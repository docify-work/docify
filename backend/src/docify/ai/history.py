"""Git history for chat: store default-branch commits, retrieve them for "who / when" questions (D63).

Ingestion is best-effort: a GitHub hiccup here never fails an index or sync job.
Privacy: only the author's display name and GitHub login are kept, never e-mail addresses.
"""

from __future__ import annotations

import asyncio
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Text, func, literal, select, text
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from docify.db.models import Commit, Repository

if TYPE_CHECKING:
    from docify.github.client import InstallationClient
    from docify.jobs.context import JobContext

HISTORY_MAX = 300  # commits listed on a full index
DETAIL_MAX = 120  # of those, how many get a per-commit call for their file list
DETAIL_CONCURRENCY = 4
FILES_PER_COMMIT = 300

_PR = re.compile(r"Merge pull request #(\d+)|\(#(\d+)\)\s*$")
_HISTORY_Q = re.compile(
    r"\b(who|whom|whose|when|author\w*|wrote|written|creat\w*|add(ed|s)?|introduc\w*|implement\w*|built|"
    r"chang\w*|modif\w*|updat\w*|commit\w*|histor\w*|contribut\w*|blame|merged?|pull request|pr|latest|"
    r"recent\w*|last|first|date|since|ago|timeline|release\w*|owner|maintain\w*)\b",
    re.IGNORECASE,
)
_FOLLOWUP = re.compile(r"\b(this|that|these|those|it|its|they|them|same|above|previous)\b", re.IGNORECASE)


def parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def pr_number(message: str) -> int | None:
    first = (message or "").splitlines()[0] if message else ""
    m = _PR.search(first)
    if not m:
        return None
    return int(m.group(1) or m.group(2))


def is_history_question(q: str) -> bool:
    return bool(_HISTORY_Q.search(q or ""))


def is_followup(q: str, key_terms: int) -> bool:
    """Short or pronoun-heavy questions ("who created this feature?") need the previous turn to retrieve."""
    return key_terms <= 3 or bool(_FOLLOWUP.search(q or ""))


def _row(repo: Repository, c: dict[str, Any]) -> dict[str, Any] | None:
    sha = str(c.get("sha") or "")
    meta = c.get("commit") or {}
    author = meta.get("author") or {}
    when = parse_ts(author.get("date")) or parse_ts((meta.get("committer") or {}).get("date"))
    if len(sha) != 40 or when is None:
        return None
    message = str(meta.get("message") or "").strip()[:4000]
    login = (c.get("author") or {}).get("login") if isinstance(c.get("author"), dict) else None
    files = [str(f.get("filename")) for f in (c.get("files") or []) if f.get("filename")][:FILES_PER_COMMIT]
    stats = c.get("stats") or {}
    return {"workspace_id": repo.workspace_id, "repo_id": repo.id, "sha": sha,
            "author_name": str(author.get("name") or login or "unknown")[:200], "author_login": login,
            "committed_at": when, "message": message, "pr_number": pr_number(message), "files": files,
            "additions": stats.get("additions"), "deletions": stats.get("deletions")}


async def record_commits(ctx: JobContext, gh: InstallationClient, repo: Repository, head: str,
                         listed: list[dict[str, Any]] | None = None) -> int:
    """Store new commits reachable from `head`. `listed` = commits from a compare (sync path); when
    None, or when this repo has no history yet (backfill), the branch history is listed."""
    try:
        async with ctx.read() as db:
            known = set((await db.execute(select(Commit.sha).where(Commit.repo_id == repo.id))).scalars())
        if listed is None or not known:
            listed = await gh.list_commits(repo.full_name, head, max_commits=HISTORY_MAX)
        new = [c for c in listed if c.get("sha") and c["sha"] not in known]
        if not new:
            return 0
        new.sort(key=lambda c: str(((c.get("commit") or {}).get("author") or {}).get("date") or ""), reverse=True)
        sem = asyncio.Semaphore(DETAIL_CONCURRENCY)

        async def detail(c: dict[str, Any]) -> dict[str, Any]:
            if c.get("files") is not None:
                return c
            async with sem:
                full = await gh.get_commit(repo.full_name, c["sha"])
            return {**c, **full} if full and full.get("sha") == c["sha"] else c

        detailed = list(await asyncio.gather(*(detail(c) for c in new[:DETAIL_MAX])))
        rows = [r for r in (_row(repo, c) for c in detailed + new[DETAIL_MAX:]) if r]
        if rows:
            async with ctx.tx() as db:
                for i in range(0, len(rows), 200):
                    await db.execute(insert(Commit).values(rows[i:i + 200])
                                     .on_conflict_do_nothing(index_elements=["repo_id", "sha"]))
        ctx.log.info("history.recorded", commits=len(rows))
    except Exception as exc:  # best-effort: history must never fail an index/sync
        ctx.log.warning("history.failed", error=type(exc).__name__)
        return 0
    await _run_checks(ctx, gh, repo, detailed, first_time=not known)
    return len(rows)


async def _run_checks(ctx: JobContext, gh: InstallationClient, repo: Repository, detailed: list[dict[str, Any]],
                      *, first_time: bool) -> None:
    """Policy checks (D66). New pushes: scan the lines each new commit added (author = that commit).
    First history for a repo: scan the current code once instead (old commits are not "new pushes")."""
    from docify import checks

    try:
        async with ctx.tx() as db:
            if first_time:
                n = await checks.scan_repo(db, repo, gh)
            else:
                oldest_first = sorted(detailed, key=lambda c: str(((c.get("commit") or {}).get("author") or {})
                                                                 .get("date") or ""))
                n = await checks.scan_pushed_commits(db, repo, oldest_first)
        ctx.log.info("checks.done", findings=n, mode="scan" if first_time else "push")
    except Exception as exc:  # best-effort, like history
        ctx.log.warning("checks.failed", error=type(exc).__name__)


# ----------------------------------------------------------------------------- retrieval


@dataclass
class CommitHit:
    repo_full_name: str
    sha: str
    author_name: str
    author_login: str | None
    committed_at: datetime
    message: str
    pr_number: int | None
    files: list[str]

    @property
    def url(self) -> str:
        return f"https://github.com/{self.repo_full_name}/commit/{self.sha}"

    @property
    def title(self) -> str:
        return self.message.splitlines()[0][:120] if self.message else self.sha[:7]

    @property
    def author(self) -> str:
        return f"{self.author_name} (@{self.author_login})" if self.author_login else self.author_name

    def as_source(self, n: int) -> dict[str, Any]:
        return {"n": n, "kind": "commit", "repo": self.repo_full_name, "commit_sha": self.sha, "url": self.url,
                "title": self.title, "author": self.author, "date": self.committed_at.isoformat()}

    def block(self, n: int) -> str:
        files = ", ".join(self.files[:15]) + (f" (+{len(self.files) - 15} more)" if len(self.files) > 15 else "")
        pr = f' pr="#{self.pr_number}"' if self.pr_number else ""
        return (f'<commit id="{n}" repo="{self.repo_full_name}" sha="{self.sha[:7]}" author="{self.author}" '
                f'date="{self.committed_at.astimezone(UTC):%Y-%m-%d %H:%M} UTC"{pr}>\n'
                f"{self.message[:1500]}\nFiles changed: {files or 'unknown'}\n</commit>")


def _hit(row: Any) -> CommitHit:
    return CommitHit(row.full_name, row.sha, row.author_name, row.author_login, row.committed_at, row.message,
                     row.pr_number, list(row.files or []))


async def relevant_commits(db: AsyncSession, *, workspace_id: uuid.UUID, repo_ids: list[uuid.UUID], query: str,
                           paths: list[str], limit: int = 8) -> list[CommitHit]:
    """Commits whose message matches the question first, then commits touching the retrieved files,
    then the most recent ones. De-duplicated, newest first within each group."""
    if not repo_ids:
        return []
    base = (select(Commit.sha, Commit.author_name, Commit.author_login, Commit.committed_at, Commit.message,
                   Commit.pr_number, Commit.files, Repository.full_name)
            .join(Repository, Repository.id == Commit.repo_id)
            .where(Commit.workspace_id == workspace_id, Commit.repo_id.in_(repo_ids)))
    queries = []
    tsq = _or_query(query)
    if tsq:
        q = func.to_tsquery("english", tsq)
        queries.append(base.where(Commit.tsv.op("@@")(q))
                       .order_by(func.ts_rank_cd(Commit.tsv, q).desc(), Commit.committed_at.desc()).limit(4))
    if paths:
        queries.append(base.where(Commit.files.op("&&")(literal(paths[:20], type_=PG_ARRAY(Text))))
                       .order_by(Commit.committed_at.desc()).limit(6))
    queries.append(base.order_by(Commit.committed_at.desc()).limit(3))
    out: dict[str, CommitHit] = {}
    for stmt in queries:
        for row in (await db.execute(stmt)).all():
            out.setdefault(row.sha, _hit(row))
    return list(out.values())[:limit]


_WORD = re.compile(r"[A-Za-z0-9_]+")
_SKIP = frozenset("who whom whose when what which where why how did does do is was were the a an this that these "
                  "those it its new feature code file files created create creates added add adds wrote written "
                  "changed change commit commits author made make by of in on for to and or".split())


def _or_query(q: str) -> str | None:
    words = sorted({w.lower() for w in _WORD.findall(q or "") if len(w) > 2 and w.lower() not in _SKIP})[:12]
    return " | ".join(words) if words else None


async def repo_facts(db: AsyncSession, repo_ids: list[uuid.UUID]) -> str:
    """One compact, non-citable block per repo: owner, creation date, first commit, contributors."""
    if not repo_ids:
        return ""
    repos = (await db.execute(select(Repository).where(Repository.id.in_(repo_ids)))).scalars().all()
    parts = []
    for r in repos:
        stats = (await db.execute(select(func.count(), func.min(Commit.committed_at), func.max(Commit.committed_at))
                                  .where(Commit.repo_id == r.id))).one()
        if not stats[0]:
            continue
        first = (await db.execute(select(Commit).where(Commit.repo_id == r.id)
                                  .order_by(Commit.committed_at).limit(1))).scalar_one()
        people = (await db.execute(select(Commit.author_name, Commit.author_login, func.count().label("n"))
                                   .where(Commit.repo_id == r.id).group_by(Commit.author_name, Commit.author_login)
                                   .order_by(text("n DESC")).limit(10))).all()
        who = ", ".join(f"{p.author_name}{f' (@{p.author_login})' if p.author_login else ''}: {p.n}" for p in people)
        created = f"{r.github_created_at:%Y-%m-%d}" if r.github_created_at else "unknown"
        first_by = f"{first.author_name}{f' (@{first.author_login})' if first.author_login else ''}"
        parts.append(
            f'<repository name="{r.full_name}" owner="{r.owner}" created_on_github="{created}" '
            f'default_branch="{r.default_branch}">\n'
            f"First commit: {first.sha[:7]} by {first_by} on {first.committed_at:%Y-%m-%d} - "
            f"{(first.message.splitlines() or [''])[0][:120]}\n"
            f"Commits indexed: {stats[0]} (from {stats[1]:%Y-%m-%d} to {stats[2]:%Y-%m-%d})\n"
            f"Contributors (commits): {who}\n</repository>")
    return "\n\n".join(parts)
