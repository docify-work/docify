"""Repository insights (D66): who did what, how active the repo is, how healthy it looks.

Most numbers come from our own tables (commits, files, findings, issues), so they cost no GitHub calls.
GitHub-only facts (stars, forks, languages, pull requests) are a snapshot cached on the repository row
for STATS_TTL and refreshed lazily when Insights is opened.
"""

from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from docify.db.models import Commit, Document, File, Finding, Issue, Repository
from docify.observability.logging import get_logger

log = get_logger(__name__)
STATS_TTL = timedelta(hours=1)
WEEKS = 26


def _area(path: str) -> str:
    parts = path.split("/")
    return parts[0] if len(parts) > 1 else "(root)"


async def refresh_github_stats(db: AsyncSession, repo: Repository, *, force: bool = False) -> None:
    fresh = repo.github_stats_at and datetime.now(UTC) - repo.github_stats_at < STATS_TTL
    if fresh and not force:
        return
    from docify.config import get_settings
    from docify.github.client import GitHubApp

    if not get_settings().github_configured:
        return
    app = GitHubApp()
    try:
        gh = await app.for_installation(repo.installation_id)
        meta = await gh.get_repo(repo.full_name, repo.github_repo_id)
        langs = await gh.languages(repo.full_name)
        pulls = await gh.list_pulls(repo.full_name)
    except Exception as exc:  # insights must render even when GitHub is unreachable
        log.info("insights.github_failed", error=type(exc).__name__)
        # Back off for STATS_TTL (keep the old snapshot) instead of retrying on every page view.
        now = datetime.now(UTC)
        await db.execute(update(Repository).where(Repository.id == repo.id).values(github_stats_at=now))
        repo.github_stats_at = now
        return
    finally:
        await app.aclose()
    merged = [p for p in pulls if p.get("merged_at")]
    hours = []
    for p in merged:
        try:
            a = datetime.fromisoformat(p["created_at"].replace("Z", "+00:00"))
            b = datetime.fromisoformat(p["merged_at"].replace("Z", "+00:00"))
            hours.append((b - a).total_seconds() / 3600)
        except (KeyError, ValueError):
            continue
    authors = Counter((p.get("user") or {}).get("login") for p in pulls if (p.get("user") or {}).get("login"))
    stats = {
        "stars": meta.get("stargazers_count", 0), "forks": meta.get("forks_count", 0),
        "watchers": meta.get("subscribers_count", meta.get("watchers_count", 0)),
        "open_issues": meta.get("open_issues_count", 0), "size_kb": meta.get("size", 0),
        "license": (meta.get("license") or {}).get("spdx_id"), "topics": meta.get("topics") or [],
        "description": meta.get("description"), "homepage": meta.get("homepage"),
        "created_at": meta.get("created_at"), "pushed_at": meta.get("pushed_at"),
        "visibility": meta.get("visibility"), "languages": langs,
        "pulls": {"total": len(pulls), "open": sum(1 for p in pulls if p.get("state") == "open"),
                  "merged": len(merged),
                  "closed_unmerged": sum(1 for p in pulls if p.get("state") == "closed" and not p.get("merged_at")),
                  "avg_hours_to_merge": round(sum(hours) / len(hours), 1) if hours else None,
                  "by_author": [{"login": k, "count": v} for k, v in authors.most_common(10)],
                  "recent": [{"number": p["number"], "title": p.get("title", "")[:200], "state": p.get("state"),
                              "merged": bool(p.get("merged_at")), "author": (p.get("user") or {}).get("login"),
                              "url": p.get("html_url"), "updated_at": p.get("updated_at")} for p in pulls[:8]]},
    }
    now = datetime.now(UTC)
    await db.execute(update(Repository).where(Repository.id == repo.id).values(github_stats=stats, github_stats_at=now))
    repo.github_stats, repo.github_stats_at = stats, now


async def repo_insights(db: AsyncSession, repo: Repository) -> dict[str, Any]:
    commits = (await db.execute(select(Commit).where(Commit.repo_id == repo.id)
                                .order_by(Commit.committed_at))).scalars().all()
    now = datetime.now(UTC)
    people: dict[str, dict[str, Any]] = {}
    areas: dict[str, Counter[str]] = defaultdict(Counter)
    churn: Counter[str] = Counter()
    file_authors: dict[str, set[str]] = defaultdict(set)
    weekly: Counter[int] = Counter()
    heat: Counter[tuple[int, int]] = Counter()
    for c in commits:
        key = c.author_login or c.author_name
        p = people.setdefault(key, {"login": c.author_login, "name": c.author_name, "commits": 0, "additions": 0,
                                    "deletions": 0, "files": set(), "prs": set(), "first": c.committed_at,
                                    "last": c.committed_at, "recent": []})
        p["commits"] += 1
        p["additions"] += c.additions or 0
        p["deletions"] += c.deletions or 0
        p["files"].update(c.files or [])
        if c.pr_number:
            p["prs"].add(c.pr_number)
        p["last"] = c.committed_at
        p["recent"] = ([{"sha": c.sha, "title": (c.message.splitlines() or [""])[0][:160],
                         "date": c.committed_at.isoformat(), "pr": c.pr_number}] + p["recent"])[:5]
        for f in c.files or []:
            areas[key][_area(f)] += 1
            churn[f] += 1
            file_authors[f].add(key)
        age_weeks = (now - c.committed_at).days // 7
        if age_weeks < WEEKS:
            weekly[WEEKS - 1 - age_weeks] += 1
        local = c.committed_at.astimezone(UTC)
        heat[(local.weekday(), local.hour)] += 1
    total = len(commits) or 1
    contributors = []
    for key, p in sorted(people.items(), key=lambda kv: kv[1]["commits"], reverse=True):
        contributors.append({
            "login": p["login"], "name": p["name"], "commits": p["commits"], "share": round(p["commits"] / total, 3),
            "additions": p["additions"], "deletions": p["deletions"], "files_touched": len(p["files"]),
            "prs": len(p["prs"]), "first_commit": p["first"].isoformat(), "last_commit": p["last"].isoformat(),
            "top_areas": [{"area": a, "changes": n} for a, n in areas[key].most_common(4)],
            "recent_commits": p["recent"],
        })
    # Bus factor: fewest people covering >= 50 % of commits.
    bus, acc = 0, 0
    for person in contributors:
        bus += 1
        acc += person["commits"]
        if acc >= total / 2:
            break
    files = (await db.execute(select(File.language, func.count(), func.coalesce(func.sum(File.line_count), 0))
                              .where(File.repo_id == repo.id).group_by(File.language))).all()
    docs = (await db.execute(select(func.count()).select_from(Document).where(
        Document.repo_id == repo.id, Document.published_version_id.is_not(None)))).scalar_one()
    findings = dict((await db.execute(select(Finding.severity, func.count()).where(
        Finding.repo_id == repo.id, Finding.status == "open").group_by(Finding.severity))).all())
    open_issues = (await db.execute(select(func.count()).select_from(Issue).where(
        Issue.repo_id == repo.id, Issue.status.in_(("open", "in_progress"))))).scalar_one()
    last = commits[-1].committed_at if commits else None
    days_since = (now - last).days if last else None
    health = _health(days_since, bus, len(contributors), docs, findings, open_issues)
    return {
        "repo": {"id": str(repo.id), "full_name": repo.full_name, "default_branch": repo.default_branch,
                 "github_created_at": repo.github_created_at.isoformat() if repo.github_created_at else None},
        "totals": {"commits": len(commits), "contributors": len(contributors),
                   "prs_merged": len({c.pr_number for c in commits if c.pr_number}),
                   "additions": sum(c.additions or 0 for c in commits),
                   "deletions": sum(c.deletions or 0 for c in commits),
                   "files": sum(n for _, n, _ in files), "lines": int(sum(lines for _, _, lines in files)),
                   "docs": docs, "open_findings": sum(findings.values()), "open_issues": open_issues,
                   "first_commit": commits[0].committed_at.isoformat() if commits else None,
                   "last_commit": last.isoformat() if last else None, "days_since_last_commit": days_since,
                   "bus_factor": bus if contributors else 0},
        "contributors": contributors,
        "weekly_commits": [{"week_start": (now - timedelta(weeks=WEEKS - 1 - i)).date().isoformat(),
                            "commits": weekly.get(i, 0)} for i in range(WEEKS)],
        "heatmap": [{"weekday": d, "hour": h, "commits": n} for (d, h), n in sorted(heat.items())],
        "hot_files": [{"path": f, "changes": n, "authors": len(file_authors[f])} for f, n in churn.most_common(10)],
        "languages": sorted(({"language": lang or "other", "files": n, "lines": int(lines)}
                             for lang, n, lines in files), key=lambda x: -x["lines"]),
        "findings_by_severity": findings,
        "health": health,
        "github": repo.github_stats,
        "github_updated_at": repo.github_stats_at.isoformat() if repo.github_stats_at else None,
    }


def _health(days_since: int | None, bus: int, people: int, docs: int, findings: dict[str, int],
            open_issues: int) -> dict[str, Any]:
    """0-100 with the reasons, so the number is explainable (tooltip in the UI)."""
    score, notes = 100, []
    if days_since is None:
        return {"score": 0, "grade": "n/a", "notes": ["No commit history yet."]}
    if days_since > 90:
        score -= 25
        notes.append(f"No commits for {days_since} days.")
    elif days_since > 30:
        score -= 10
        notes.append(f"Last commit {days_since} days ago.")
    if people and bus <= 1:
        score -= 15
        notes.append("Bus factor 1: one person wrote most of the code.")
    if docs < 3:
        score -= 10
        notes.append("Not all docs are published.")
    weights = {"critical": 20, "high": 10, "medium": 4, "low": 1, "info": 0}
    penalty = min(35, sum(weights.get(k, 0) * v for k, v in findings.items()))
    if penalty:
        score -= penalty
        notes.append(f"{sum(findings.values())} open policy finding(s).")
    if open_issues:
        score -= min(15, open_issues * 3)
        notes.append(f"{open_issues} open issue(s).")
    score = max(0, score)
    grade = "A" if score >= 85 else "B" if score >= 70 else "C" if score >= 50 else "D"
    if not notes:
        notes.append("Active, documented, no open findings or issues.")
    return {"score": score, "grade": grade, "notes": notes}


async def workspace_contributors(db: AsyncSession, workspace_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = (await db.execute(select(Commit.author_login, Commit.author_name, func.count(),
                                    func.max(Commit.committed_at))
                             .where(Commit.workspace_id == workspace_id)
                             .group_by(Commit.author_login, Commit.author_name)
                             .order_by(func.count().desc()))).all()
    merged: dict[str, dict[str, Any]] = {}
    for login, name, n, last in rows:
        key = login or name
        m = merged.setdefault(key, {"login": login, "name": name, "commits": 0, "last_commit": last})
        m["commits"] += n
        m["last_commit"] = max(m["last_commit"], last)
    return sorted(merged.values(), key=lambda x: -x["commits"])
