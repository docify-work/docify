"""Generate / update the three repo documents and changelog entries (Master Doc §11.3, D36)."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from sqlalchemy import func, select, text, update

from docify.ai import citations, prompts
from docify.ai.budget import check_budget, estimate_tokens, record_llm
from docify.ai.indexer import file_text
from docify.ai.llm import LLMRefusal, LLMTruncated
from docify.db.models import ChangelogEntry, Document, DocumentVersion, File, Repository, Workspace
from docify.jobs.context import JobContext

DOC_KINDS = ("overview", "setup", "api")
DOC_TITLES = {"overview": "Overview", "setup": "Setup guide", "api": "API reference"}
DOC_INPUT_TOKENS = 60_000
MAX_FILE_CHARS = 16_000

MANIFESTS = re.compile(
    r"(^|/)(package\.json|pyproject\.toml|go\.mod|pom\.xml|build\.gradle(\.kts)?|Cargo\.toml|Gemfile|composer\.json|"
    r"requirements[^/]*\.txt|Dockerfile[^/]*|docker-compose[^/]*\.ya?ml|compose\.ya?ml)$"
)
WORKFLOWS = re.compile(r"^\.github/workflows/[^/]+\.ya?ml$")
SETUP_EXTRA = re.compile(r"(^|/)(Makefile|justfile|\.env\.example|\.env\.sample|config\.[a-z]+|settings\.[a-z]+)$")
README = re.compile(r"^readme(\.[a-z]+)?$", re.I)
# Postgres regex (ARE): `\y` is a word boundary (`\b` would mean backspace).
ROUTE_SQL = (r"(@(app|router|bp|blueprint)\.(get|post|put|patch|delete|route)\y|\y(app|router)\."
             r"(get|post|put|patch|delete)\(|@(Get|Post|Put|Patch|Delete|Request)Mapping|HandleFunc\(|"
             r"\.(GET|POST|PUT|PATCH|DELETE)\(|path\(['\"])")


@dataclass
class Material:
    path: str
    body: str
    priority: int  # lower = more important

    @property
    def tokens(self) -> int:
        return estimate_tokens(self.body)


def numbered(text_: str, limit: int = MAX_FILE_CHARS) -> str:
    out, size = [], 0
    for i, line in enumerate(text_.split("\n"), 1):
        row = f"{i:>4}| {line}"
        size += len(row) + 1
        if size > limit:
            out.append("     … (truncated)")
            break
        out.append(row)
    return "\n".join(out)


def tree(paths: list[str], depth: int = 3, limit: int = 400) -> str:
    seen: set[str] = set()
    lines: list[str] = []
    for p in sorted(paths):
        parts = PurePosixPath(p).parts
        for d in range(1, min(len(parts), depth) + 1):
            key = "/".join(parts[:d]) + ("/" if d < len(parts) else "")
            if key not in seen:
                seen.add(key)
                lines.append("  " * (d - 1) + parts[d - 1] + ("/" if d < len(parts) else ""))
                if len(lines) >= limit:
                    return "\n".join([*lines, "…"])
    return "\n".join(lines)


async def _route_files(ctx: JobContext, repo_id: uuid.UUID) -> list[str]:
    async with ctx.read() as db:
        rows = (await db.execute(text(
            "SELECT DISTINCT path FROM chunks WHERE repo_id = :r AND content ~ :pat ORDER BY path LIMIT 60"
        ), {"r": repo_id, "pat": ROUTE_SQL})).scalars().all()
        urls = (await db.execute(select(File.path).where(File.repo_id == repo_id, File.path.like("%urls.py"))))
        return sorted(set(rows) | set(urls.scalars().all()))


async def _materials(ctx: JobContext, repo: Repository, kind: str) -> tuple[list[Material], dict[str, int]]:
    async with ctx.read() as db:
        files = (await db.execute(select(File.id, File.path, File.summary, File.line_count, File.language)
                                  .where(File.repo_id == repo.id))).all()
    by_path = {f.path: f for f in files}
    line_counts = {f.path: f.line_count for f in files}
    mats: list[Material] = [Material("(tree)", "Repository tree (depth 3):\n" + tree(list(by_path)), 0)]

    async def full(path: str, prio: int) -> None:
        f = by_path.get(path)
        if f is not None:
            mats.append(Material(path, f"### {path}\n```\n{numbered(await file_text(ctx, f.id))}\n```", prio))

    readmes = [p for p in by_path if README.match(PurePosixPath(p).name) and "/" not in p]
    for p in readmes[:1]:
        await full(p, 1)
    manifests = sorted(p for p in by_path if MANIFESTS.search(p))
    for p in manifests[:12]:
        await full(p, 2 + p.count("/"))

    if kind == "overview":
        groups: dict[str, list[str]] = {}
        for f in files:
            if f.summary:
                top = f.path.split("/")[0] if "/" in f.path else "(root)"
                groups.setdefault(top, []).append(f"- `{f.path}` — {f.summary}")
        for top, items in sorted(groups.items()):
            for i in range(0, len(items), 40):
                mats.append(Material(f"(summaries:{top})", f"### Summaries: {top}/\n" + "\n".join(items[i:i + 40]),
                                     5 + i // 40))
    elif kind == "setup":
        for p in sorted(p for p in by_path if WORKFLOWS.match(p))[:6]:
            await full(p, 4)
        for p in sorted(p for p in by_path if SETUP_EXTRA.search(p))[:10]:
            await full(p, 3 + p.count("/"))
    elif kind == "api":
        for p in (await _route_files(ctx, repo.id))[:30]:
            await full(p, 2 + p.count("/"))
            fs = by_path.get(p)
            if fs is not None and fs.summary:
                mats.append(Material(f"(summary:{p})", f"- `{p}` — {fs.summary}", 3))
    return mats, line_counts


def _select(mats: list[Material], budget: int) -> tuple[list[Material], bool]:
    chosen, used, partial = [], 0, False
    for m in sorted(mats, key=lambda m: (m.priority, m.path)):
        if used + m.tokens > budget:
            partial = True
            continue
        chosen.append(m)
        used += m.tokens
    return chosen, partial


def source_paths(mats: list[Material]) -> list[str]:
    return sorted({m.path for m in mats if not m.path.startswith("(")})


async def _base_version(db: Any, document: Document) -> DocumentVersion | None:
    pending = (await db.execute(select(DocumentVersion).where(
        DocumentVersion.document_id == document.id, DocumentVersion.status == "pending_review")
        .order_by(DocumentVersion.version.desc()).limit(1))).scalar_one_or_none()
    if pending is not None:
        return pending
    if document.published_version_id:
        return await db.get(DocumentVersion, document.published_version_id)
    return None


async def generate_doc(ctx: JobContext, repo: Repository, kind: str, sha: str, *,
                       change_note: str | None = None) -> bool:
    """Create a new version of one document. Returns False if skipped (refusal/budget)."""
    mats, line_counts = await _materials(ctx, repo, kind)
    async with ctx.read() as db:
        await check_budget(db, repo.workspace_id)
        doc = (await db.execute(select(Document).where(Document.repo_id == repo.id, Document.kind == kind)))\
            .scalar_one_or_none()
        base = await _base_version(db, doc) if doc is not None else None
        ws_row = await db.get(Workspace, repo.workspace_id)
        settings = ws_row.settings if ws_row else {}
    budget = DOC_INPUT_TOKENS
    header = f"Repository: {repo.full_name} (default branch {repo.default_branch}, commit {sha[:12]})\n" \
             f"{prompts.DOC_OUTLINES[kind]}\n"
    update_part = ""
    if base is not None and change_note is not None:
        update_part = f"\n{prompts.DOC_UPDATE_NOTE}\n\n<current_document>\n{base.content_md}\n</current_document>\n" \
                      f"\n<changes>\n{change_note}\n</changes>\n"
        budget -= estimate_tokens(update_part)
    chosen, partial = _select(mats, max(budget, 8_000))
    material = "\n\n".join(m.body for m in chosen)
    user = f"{header}{update_part}\n<repository_material>\n{material}\n</repository_material>"
    est = estimate_tokens(user)
    if not ctx.meter.can_spend(est):
        partial = True
        return False
    ctx.meter.spend(est)
    model = ctx.settings.llm_model_doc
    try:
        res = await ctx.llm.complete(task="doc", model=model, system=prompts.DOC_SYSTEM, max_tokens=8000,
                                     messages=[{"role": "user", "content": user}])
    except LLMTruncated:
        # F19: one retry with half the material.
        chosen, partial = _select(mats, max(budget // 2, 6_000))
        user = f"{header}{update_part}\n<repository_material>\n" + "\n\n".join(m.body for m in chosen) + \
            "\n</repository_material>"
        res = await ctx.llm.complete(task="doc", model=model, system=prompts.DOC_SYSTEM, max_tokens=8000,
                                     messages=[{"role": "user", "content": user}])
        partial = True
    except LLMRefusal:
        ctx.log.warning("docgen.refusal", kind=kind)
        return False
    content, _removed = citations.validate(res.text.strip(), line_counts)
    if not content.lstrip().startswith("#"):
        content = f"# {DOC_TITLES[kind]}\n\n{content}"
    title = content.lstrip().split("\n", 1)[0].lstrip("# ").strip()[:200] or DOC_TITLES[kind]
    auto = bool((settings or {}).get("auto_publish", True))
    async with ctx.tx() as db:
        record_llm(db, workspace_id=repo.workspace_id, job_id=ctx.job_id, purpose=f"doc_{kind}", model=res.model,
                   usage=res.usage)
        await save_version(db, repo=repo, kind=kind, title=title, content=content, sha=sha, model=res.model,
                           sources=source_paths(chosen), partial=partial, auto_publish=auto, job_id=ctx.job_id)
    return True


async def save_version(db: Any, *, repo: Repository, kind: str, title: str, content: str, sha: str, model: str,
                       sources: list[str], partial: bool, auto_publish: bool,
                       job_id: uuid.UUID | None) -> DocumentVersion:
    doc = (await db.execute(select(Document).where(Document.repo_id == repo.id, Document.kind == kind)
                            .with_for_update())).scalar_one_or_none()
    if doc is None:
        doc = Document(workspace_id=repo.workspace_id, repo_id=repo.id, kind=kind, title=title, source_paths=sources)
        db.add(doc)
        await db.flush()
    base = await _base_version(db, doc)
    next_v = (await db.execute(select(func.coalesce(func.max(DocumentVersion.version), 0))
                               .where(DocumentVersion.document_id == doc.id))).scalar_one() + 1
    status = "published" if auto_publish else "pending_review"
    # Only one pending version at a time: older pending ones are superseded (§11.3 item 4).
    await db.execute(update(DocumentVersion).where(DocumentVersion.document_id == doc.id,
                                                   DocumentVersion.status == "pending_review")
                     .values(status="superseded"))
    ver = DocumentVersion(workspace_id=repo.workspace_id, document_id=doc.id, version=next_v,
                          base_version_id=base.id if base else None, content_md=content, commit_sha=sha, job_id=job_id,
                          model=model, status=status, partial=partial)
    db.add(ver)
    await db.flush()
    doc.source_paths = sources
    if auto_publish:
        doc.published_version_id = ver.id
        doc.title = title
    return ver


def docs_to_update(changed: set[str], added_or_removed: set[str], docs: dict[str, list[str]],
                   route_files: set[str]) -> list[str]:
    """§11.3 item 3 update rule."""
    manifests_changed = any(MANIFESTS.search(p) or README.match(PurePosixPath(p).name) for p in changed)
    out = []
    for kind in DOC_KINDS:
        sources = set(docs.get(kind, []))
        if kind not in docs or changed & sources or (kind in ("overview", "setup") and manifests_changed) or \
                (kind == "api" and (added_or_removed & route_files or changed & route_files)):
            out.append(kind)
    return out


PR_REF = re.compile(r"(?:#|pull request #)(\d+)")


async def write_changelog(ctx: JobContext, repo: Repository, *, from_sha: str | None, to_sha: str,
                          commits: list[dict[str, Any]], changed: list[str]) -> bool:
    messages = [str((c.get("commit") or {}).get("message", "")).strip() for c in commits][-50:]
    prs = sorted({int(n) for m in messages for n in PR_REF.findall(m)})[:30]
    async with ctx.read() as db:
        await check_budget(db, repo.workspace_id)
        summaries = (await db.execute(select(File.path, File.summary).where(
            File.repo_id == repo.id, File.path.in_(changed[:80] or [""])))).all()
        ws_row = await db.get(Workspace, repo.workspace_id)
        settings = ws_row.settings if ws_row else {}
    body = ("Commits (oldest first):\n" + "\n".join(f"- {m.splitlines()[0][:200]}" for m in messages if m)
            + (f"\n\nPull requests: {', '.join('#' + str(p) for p in prs)}" if prs else "")
            + "\n\nChanged files:\n" + "\n".join(f"### {p}\n{s or ''}" for p, s in summaries)
            + ("\n" + "\n".join(f"### {p}" for p in changed[80:120]) if len(changed) > 80 else ""))
    try:
        res = await ctx.llm.complete(task="changelog", model=ctx.settings.llm_model_summary,
                                     system=prompts.CHANGELOG_SYSTEM, max_tokens=800,
                                     messages=[{"role": "user", "content": body}])
    except (LLMRefusal, LLMTruncated):
        return False
    auto = bool((settings or {}).get("auto_publish", True))
    async with ctx.tx() as db:
        record_llm(db, workspace_id=repo.workspace_id, job_id=ctx.job_id, purpose="changelog", model=res.model,
                   usage=res.usage)
        db.add(ChangelogEntry(workspace_id=repo.workspace_id, repo_id=repo.id, from_sha=from_sha, to_sha=to_sha,
                              content_md=res.text.strip()[:8000], pr_numbers=prs,
                              status="published" if auto else "pending_review", job_id=ctx.job_id))
    return True
