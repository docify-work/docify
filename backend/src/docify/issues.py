"""Issue triage (D66): who most likely introduced a bug, with evidence, so an admin can assign it.

Signals, strongest first (scores add up per person, then are normalised to 0-1 "confidence"):
1. A linked policy finding -> the commit author who added the flagged line.
2. Files named in the issue -> GitHub blame of those files (share of lines) + recent commits touching them.
3. Code the issue text is about (hybrid search over the indexed code) -> blame of the matching line ranges.
4. Commits whose message matches the issue text.
Every reason carries a link (commit / file lines) so a human can check it before assigning.
"""

from __future__ import annotations

import re
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from docify.checks import touches
from docify.db.models import Commit, Finding, Issue, Repository
from docify.observability.logging import get_logger

log = get_logger(__name__)
MAX_BLAME_CALLS = 6
_PATHLIKE = re.compile(r"(?<![\w/.-])([\w.-]+(?:/[\w.-]+)+\.\w{1,6}|[\w-]+\.(?:py|ts|tsx|js|jsx|go|rs|java|rb|"
                       r"css|html|md|ya?ml|json|toml|sql|sh|tf|vue|svelte|php|cs|kt|swift))(?::(\d+))?")


def mentioned_paths(text_: str) -> list[str]:
    return list(dict.fromkeys(m.group(1) for m in _PATHLIKE.finditer(text_ or "")))[:10]


class _Board:
    def __init__(self) -> None:
        self.people: dict[str, dict[str, Any]] = {}

    def add(self, login: str | None, name: str | None, score: float, reason: str, url: str | None) -> None:
        key = login or name or "unknown"
        p = self.people.setdefault(key, {"login": login, "name": name or login or "unknown", "score": 0.0,
                                         "reasons": []})
        p["score"] += score
        if len(p["reasons"]) < 6 and not any(r["text"] == reason for r in p["reasons"]):
            p["reasons"].append({"text": reason, "url": url})

    def ranked(self, limit: int = 5) -> list[dict[str, Any]]:
        items = sorted(self.people.values(), key=lambda p: -p["score"])[:limit]
        top = items[0]["score"] if items else 1.0
        for p in items:
            p["confidence"] = round(p["score"] / max(top, 1e-9), 2)
            p["score"] = round(p["score"], 3)
        return items


def _commit_url(full_name: str, sha: str) -> str:
    return f"https://github.com/{full_name}/commit/{sha}"


async def analyze(db: AsyncSession, issue: Issue, repos: list[Repository]) -> list[dict[str, Any]]:
    board = _Board()
    by_id = {r.id: r for r in repos}
    text_ = f"{issue.title}\n{issue.body or ''}"

    # 1) Linked finding.
    if issue.finding_id:
        f = await db.get(Finding, issue.finding_id)
        if f is not None and (f.author_login or f.author_name):
            repo = by_id.get(f.repo_id)
            url = _commit_url(repo.full_name, f.commit_sha) if repo and f.commit_sha else None
            board.add(f.author_login, f.author_name, 6.0,  # exact line: strongest evidence
                      f"Added the flagged line {f.path}:{f.line or '?'} ({f.policy_name})"
                      + (f" in {f.commit_sha[:7]}" if f.commit_sha else ""), url)

    gh_app, clients = None, {}
    blame_calls = 0

    async def blame(repo: Repository, path: str) -> list[dict[str, Any]]:
        nonlocal gh_app, blame_calls
        from docify.config import get_settings
        from docify.github.client import GitHubApp

        if blame_calls >= MAX_BLAME_CALLS or not repo.last_processed_sha or not get_settings().github_configured:
            return []
        blame_calls += 1
        try:
            if gh_app is None:
                gh_app = GitHubApp()
            if repo.installation_id not in clients:
                clients[repo.installation_id] = await gh_app.for_installation(repo.installation_id)
            return await clients[repo.installation_id].blame(repo.full_name, repo.last_processed_sha, path)
        except Exception as exc:
            log.info("issues.blame_failed", error=type(exc).__name__)
            return []

    def credit_ranges(repo: Repository, path: str, ranges: list[dict[str, Any]], lo: int | None, hi: int | None,
                      weight: float, why: str) -> bool:
        lines: dict[tuple[str | None, str | None], int] = defaultdict(int)
        sample: dict[tuple[str | None, str | None], dict[str, Any]] = {}
        for r in ranges:
            a, b = r["start"], r["end"]
            if lo is not None and hi is not None:
                a, b = max(a, lo), min(b, hi)
            if b < a:
                continue
            k = (r["login"], None if r["login"] else r["name"])  # one entry per person, not per name spelling
            lines[k] += b - a + 1
            if k not in sample or (r["date"] and sample[k]["date"] and r["date"] > sample[k]["date"]):
                sample[k] = r
        total = sum(lines.values())
        for key, n in lines.items():
            r = sample[key]
            login = key[0]
            name = r["name"]
            share = n / total
            span = f"{path}:{lo}-{hi}" if lo else path
            board.add(login, name, weight * share,
                      (f"Wrote {round(share * 100)}% of {span} ({why}), last in {r['sha'][:7]}: "
                       f"{r['message'] or ''}")[:300],
                      _commit_url(repo.full_name, r["sha"]))
        return total > 0

    async def credit_commits(repo: Repository, path: str, weight: float, why: str) -> None:
        rows = (await db.execute(select(Commit).where(Commit.repo_id == repo.id, touches(path))
                                 .order_by(Commit.committed_at.desc()).limit(5))).scalars().all()
        for i, c in enumerate(rows):
            board.add(c.author_login, c.author_name, weight / (i + 1),
                      f"Changed {path} in {c.sha[:7]} ({c.committed_at:%Y-%m-%d}): {c.message.splitlines()[0][:120]}"
                      f" — {why}", _commit_url(repo.full_name, c.sha))

    # 2) Files named in the issue (or set explicitly on it).
    paths = list(dict.fromkeys([*(issue.paths or []), *mentioned_paths(text_)]))
    scoped = [by_id[issue.repo_id]] if issue.repo_id in by_id else repos
    known: list[tuple[Repository, str]] = []
    for path in paths:
        for repo in scoped:
            hit = (await db.execute(select(func.count()).select_from(Commit).where(
                Commit.repo_id == repo.id, touches(path)))).scalar_one()
            if hit:
                known.append((repo, path))
                break
    for repo, path in known[:4]:
        if not credit_ranges(repo, path, await blame(repo, path), None, None, 2.0, "file named in the issue"):
            await credit_commits(repo, path, 1.5, "file named in the issue")

    # 3) Code the issue is about (hybrid retrieval).
    try:
        from docify.ai.embeddings import get_embedder
        from docify.ai.rag import retrieve

        hits, has_context = await retrieve(db, workspace_id=issue.workspace_id, repo_ids=[r.id for r in scoped],
                                           query=text_[:2000], embedder=get_embedder())
    except Exception as exc:
        log.info("issues.retrieve_failed", error=type(exc).__name__)
        hits, has_context = [], False
    if has_context:
        for h in hits[:3]:
            repo = by_id.get(h.repo_id)
            if repo is None or (repo, h.path) in known:
                continue
            ranges = await blame(repo, h.path)
            if not credit_ranges(repo, h.path, ranges, h.start_line, h.end_line, 1.0, "code matching the issue"):
                await credit_commits(repo, h.path, 0.6, "code matching the issue")

    # 4) Commits whose message matches the issue.
    from docify.ai.history import _or_query

    tsq = _or_query(text_)
    if tsq:
        q = func.to_tsquery("english", tsq)
        rows = (await db.execute(select(Commit, Repository.full_name).join(Repository, Repository.id == Commit.repo_id)
                                 .where(Commit.repo_id.in_([r.id for r in scoped]), Commit.tsv.op("@@")(q))
                                 .order_by(func.ts_rank_cd(Commit.tsv, q).desc()).limit(4))).all()
        for c, full_name in rows:
            board.add(c.author_login, c.author_name, 0.5,
                      f"Commit {c.sha[:7]} message matches the issue: {c.message.splitlines()[0][:120]}",
                      _commit_url(full_name, c.sha))
    if gh_app is not None:
        await gh_app.aclose()
    return board.ranked()


async def next_number(db: AsyncSession, workspace_id: uuid.UUID) -> int:
    n = (await db.execute(select(func.max(Issue.number)).where(Issue.workspace_id == workspace_id))).scalar_one()
    return (n or 0) + 1


def now() -> datetime:
    return datetime.now(UTC)
