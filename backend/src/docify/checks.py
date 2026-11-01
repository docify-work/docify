"""Policy checks (D66): flag lines that break a workspace's rules, and say who introduced them.

Two entry points:
- `scan_pushed_commits` — every new commit on the default branch (push / merged PR): only the lines that commit
  ADDED are checked, so each finding is attributed to that commit's author.
- `scan_repo` — "Scan now" / first index: the current code is checked; the author comes from GitHub blame
  (GraphQL) when available, else from the last commit that touched the file.

Patterns are user input: length-capped, compiled once, and refused when they look catastrophic (nested
quantifiers); lines are truncated before matching. Secrets are redacted before anything is stored.
"""

from __future__ import annotations

import fnmatch
import hashlib
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import ColumnElement, Text, literal, select
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from docify.db.models import Chunk, Commit, Finding, Policy, Repository

if TYPE_CHECKING:
    from docify.github.client import InstallationClient

MAX_PATTERN = 500
MAX_LINE = 400
MAX_FINDINGS_PER_RUN = 300
BLAME_MAX_FILES = 25

# ----------------------------------------------------------------------------- templates

TEMPLATES: dict[str, dict[str, Any]] = {
    "secrets": {
        "name": "No secrets or API keys",
        "description": "Cloud keys, tokens, private keys and hard-coded passwords must never be committed.",
        "kind": "regex", "severity": "critical", "paths": "", "enabled": True,
        "pattern": (r"AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{40,}"
                    r"|xox[baprs]-[A-Za-z0-9-]{10,}|sk-[A-Za-z0-9_-]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----"
                    r"|(?i:(?:api[_-]?key|secret|passwd|password|token)[\"']?\s*[:=]\s*[\"'][^\"'\s]{8,}[\"'])"),
    },
    "ai_models": {
        "name": "No AI model names in the product",
        "description": "Model and vendor names (GPT, Claude, Gemini, Llama, Nova...) must not appear in user-facing "
                       "code or copy.",
        "kind": "regex", "severity": "medium", "paths": "", "enabled": True,
        "pattern": (r"(?i)\b(gpt-?(3\.5|4o?|4\.1|5)(-mini|-turbo)?|chatgpt|claude([- ](opus|sonnet|haiku|\d))?"
                    r"|gemini([- ]\d(\.\d)?)?|llama[- ]?\d|mistral|mixtral|nova[- ](micro|lite|pro))\b"),
    },
    "debug": {
        "name": "No debug leftovers",
        "description": "console.log / debugger / print-debugging should not reach the default branch.",
        "kind": "regex", "severity": "low", "paths": "*.js,*.jsx,*.ts,*.tsx,*.mjs,*.vue,*.svelte",
        "enabled": True, "pattern": r"\bconsole\.(log|debug)\(|\bdebugger\s*;",
    },
    "todo": {
        "name": "No TODO / FIXME",
        "description": "Unfinished work markers. Off by default: turn on when you want a clean main branch.",
        "kind": "terms", "severity": "info", "paths": "", "enabled": False, "pattern": "TODO\nFIXME\nHACK\nXXX",
    },
    "ip_addresses": {
        "name": "No hard-coded IP addresses",
        "description": "Use configuration or DNS names instead of literal IPv4 addresses.",
        "kind": "regex", "severity": "low", "paths": "", "enabled": False,
        "pattern": r"\b(?!127\.0\.0\.1|0\.0\.0\.0)(?:\d{1,3}\.){3}\d{1,3}\b",
    },
}
REDACT_TEMPLATES = {"secrets"}

_NESTED = re.compile(r"\((?:[^()\\]|\\.)*[+*](?:[^()\\]|\\.)*\)\s*[+*{]")


def touches(path: str) -> ColumnElement[bool]:
    """Commit.files @> ARRAY[path] (uses the GIN index)."""
    return Commit.files.op("@>")(literal([path], type_=PG_ARRAY(Text)))


class PolicyError(ValueError):
    pass


def compile_pattern(kind: str, pattern: str) -> re.Pattern[str]:
    pattern = (pattern or "").strip()
    if not pattern or len(pattern) > MAX_PATTERN:
        raise PolicyError(f"Pattern must be 1-{MAX_PATTERN} characters.")
    if kind == "terms":
        terms = [t.strip() for t in pattern.splitlines() if t.strip()]
        if not terms:
            raise PolicyError("Add at least one term.")
        return re.compile(r"(?i)(?<![\w])(" + "|".join(re.escape(t) for t in terms) + r")(?![\w])")
    if _NESTED.search(pattern):
        raise PolicyError("Nested quantifiers like (a+)+ are not allowed (they can hang the scanner).")
    try:
        return re.compile(pattern)
    except re.error as exc:
        raise PolicyError(f"Invalid regular expression: {exc}") from exc


def path_matches(globs: str | None, path: str) -> bool:
    items = [g.strip() for g in (globs or "").split(",") if g.strip()]
    if not items:
        return True
    name = path.rsplit("/", 1)[-1]
    return any(fnmatch.fnmatch(path, g) or fnmatch.fnmatch(name, g) for g in items)


def added_lines(patch: str | None) -> list[tuple[int, str]]:
    """Lines added by a unified diff, with their line numbers in the new file."""
    out: list[tuple[int, str]] = []
    line = 0
    for raw in (patch or "").splitlines():
        if raw.startswith("@@"):
            m = re.search(r"\+(\d+)", raw)
            line = int(m.group(1)) if m else 0
            continue
        if raw.startswith("+") and not raw.startswith("+++"):
            out.append((line, raw[1:]))
            line += 1
        elif raw.startswith(("-", "\\")):  # removed line / "\ No newline at end of file"
            continue
        else:
            line += 1
    return out


def redact(text_: str, match: str) -> str:
    keep = match[:4]
    return text_.replace(match, keep + "…[redacted]")


@dataclass
class CompiledPolicy:
    id: uuid.UUID
    name: str
    severity: str
    paths: str | None
    regex: re.Pattern[str]
    redact: bool


@dataclass
class Hit:
    policy: CompiledPolicy
    path: str
    line: int | None
    snippet: str
    match: str


def compile_policies(policies: list[Policy]) -> list[CompiledPolicy]:
    out = []
    for p in policies:
        if not p.enabled:
            continue
        try:
            rx = compile_pattern(p.kind, p.pattern)
        except PolicyError:
            continue
        out.append(CompiledPolicy(p.id, p.name, p.severity, p.paths, rx, p.template in REDACT_TEMPLATES))
    return out


def scan_lines(policies: list[CompiledPolicy], path: str, lines: list[tuple[int | None, str]]) -> list[Hit]:
    hits: list[Hit] = []
    for p in policies:
        if not path_matches(p.paths, path):
            continue
        for no, raw in lines:
            text_ = raw[:MAX_LINE]
            m = p.regex.search(text_)
            if not m or not m.group(0).strip():
                continue
            snippet = text_.strip()
            matched = m.group(0)
            if p.redact:
                snippet, matched = redact(snippet, matched), matched[:4] + "…"
            hits.append(Hit(p, path, no, snippet[:300], matched[:200]))
    return hits


def fingerprint(policy_id: uuid.UUID, path: str, snippet: str) -> str:
    norm = " ".join(snippet.split())
    return hashlib.sha256(f"{policy_id}|{path}|{norm}".encode()).hexdigest()


async def ensure_default_policies(db: AsyncSession, workspace_id: uuid.UUID) -> None:
    have = set((await db.execute(select(Policy.template).where(Policy.workspace_id == workspace_id))).scalars())
    if have:  # defaults are created once; deleted templates stay deleted
        return
    for key, t in TEMPLATES.items():
        db.add(Policy(workspace_id=workspace_id, name=t["name"], description=t["description"], kind=t["kind"],
                      pattern=t["pattern"], severity=t["severity"], paths=t["paths"] or None,
                      enabled=t["enabled"], template=key))
    await db.flush()


async def load_policies(db: AsyncSession, workspace_id: uuid.UUID) -> list[CompiledPolicy]:
    await ensure_default_policies(db, workspace_id)
    rows = (await db.execute(select(Policy).where(Policy.workspace_id == workspace_id))).scalars().all()
    return compile_policies(list(rows))


async def _store(db: AsyncSession, repo: Repository, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    res = await db.execute(insert(Finding).values(rows[:MAX_FINDINGS_PER_RUN])
                           .on_conflict_do_nothing(index_elements=["repo_id", "fingerprint"])
                           .returning(Finding.id))
    return len(res.all())


_ATTRIB_KEYS = ("commit_sha", "commit_message", "author_name", "author_login", "committed_at", "pr_number", "note")


def _row(repo: Repository, h: Hit, source: str, **attrib: Any) -> dict[str, Any]:
    # Every row needs the same keys: a multi-row INSERT renders one VALUES shape.
    attrib = {k: attrib.get(k) for k in _ATTRIB_KEYS}
    return {"workspace_id": repo.workspace_id, "repo_id": repo.id, "policy_id": h.policy.id,
            "policy_name": h.policy.name, "severity": h.policy.severity, "status": "open", "source": source,
            "fingerprint": fingerprint(h.policy.id, h.path, h.snippet), "path": h.path, "line": h.line,
            "snippet": h.snippet, "match": h.match, **attrib}


# ----------------------------------------------------------------------------- push path


async def scan_pushed_commits(db: AsyncSession, repo: Repository, commits: list[dict[str, Any]]) -> int:
    """`commits` = GitHub commit objects WITH `files[].patch` (from GET /commits/{sha}), oldest first."""
    policies = await load_policies(db, repo.workspace_id)
    if not policies:
        return 0
    rows: list[dict[str, Any]] = []
    # A merged PR arrives as feature commits + one merge commit ("Merge pull request #N"): the flagged line is
    # in a feature commit, so give every commit of this push the PR number found in it.
    push_pr = next((n for n in (_pr(str((c.get("commit") or {}).get("message") or "")) for c in commits) if n), None)
    for c in commits:
        meta = c.get("commit") or {}
        author = meta.get("author") or {}
        message = str(meta.get("message") or "")
        login = (c.get("author") or {}).get("login") if isinstance(c.get("author"), dict) else None
        when = author.get("date")
        attrib = {"commit_sha": c.get("sha"), "commit_message": message.splitlines()[0][:300] if message else None,
                  "author_name": str(author.get("name") or login or "unknown")[:200], "author_login": login,
                  "committed_at": datetime.fromisoformat(str(when).replace("Z", "+00:00")) if when else None,
                  "pr_number": _pr(message) or push_pr}
        for f in c.get("files") or []:
            if f.get("status") == "removed" or not f.get("patch"):
                continue
            lines: list[tuple[int | None, str]] = list(added_lines(f["patch"]))
            for h in scan_lines(policies, f["filename"], lines):
                rows.append(_row(repo, h, "push", **attrib))
    return await _store(db, repo, rows)


def _pr(message: str) -> int | None:
    from docify.ai.history import pr_number

    return pr_number(message)


# ----------------------------------------------------------------------------- full scan


async def current_files(db: AsyncSession, repo_id: uuid.UUID) -> dict[str, list[tuple[int | None, str]]]:
    """Current file lines rebuilt from the indexed chunks (chunks overlap: keep the first copy of a line)."""
    rows = (await db.execute(select(Chunk.path, Chunk.start_line, Chunk.content).where(Chunk.repo_id == repo_id)
                             .order_by(Chunk.path, Chunk.start_line))).all()
    files: dict[str, dict[int, str]] = {}
    for path, start, content in rows:
        seen = files.setdefault(path, {})
        for i, line in enumerate(content.split("\n")):
            seen.setdefault(start + i, line)
    return {p: [(n, t) for n, t in sorted(lines.items())] for p, lines in files.items()}


async def scan_repo(db: AsyncSession, repo: Repository, gh: InstallationClient | None = None) -> int:
    policies = await load_policies(db, repo.workspace_id)
    if not policies:
        return 0
    hits: list[Hit] = []
    for path, lines in (await current_files(db, repo.id)).items():
        hits.extend(scan_lines(policies, path, lines))
    if not hits:
        return 0
    # Who wrote each flagged line: GitHub blame (exact) -> last commit touching the file (approximate).
    blame: dict[str, list[dict[str, Any]]] = {}
    if gh is not None and repo.last_processed_sha:
        for path in list(dict.fromkeys(h.path for h in hits))[:BLAME_MAX_FILES]:
            try:
                blame[path] = await gh.blame(repo.full_name, repo.last_processed_sha, path)
            except Exception:
                blame[path] = []
    last_touch: dict[str, Commit] = {}
    for h in hits:
        if h.path in last_touch:
            continue
        c = (await db.execute(select(Commit).where(Commit.repo_id == repo.id, touches(h.path))
                              .order_by(Commit.committed_at.desc()).limit(1))).scalar_one_or_none()
        if c is not None:
            last_touch[h.path] = c
    rows = []
    for h in hits:
        attrib: dict[str, Any] = {}
        rng = next((r for r in blame.get(h.path, []) if h.line and r["start"] <= h.line <= r["end"]), None)
        if rng is not None:
            attrib = {"commit_sha": rng["sha"], "commit_message": rng["message"], "author_name": rng["name"],
                      "author_login": rng["login"], "committed_at": rng["date"], "pr_number": _pr(rng["message"] or "")}
        elif h.path in last_touch:
            c = last_touch[h.path]
            attrib = {"commit_sha": c.sha, "commit_message": c.message.splitlines()[0][:300] if c.message else None,
                      "author_name": c.author_name, "author_login": c.author_login, "committed_at": c.committed_at,
                      "pr_number": c.pr_number, "note": "Author = last commit that changed this file (no blame)."}
        rows.append(_row(repo, h, "scan", **attrib))
    return await _store(db, repo, rows)


def now() -> datetime:
    return datetime.now(UTC)
