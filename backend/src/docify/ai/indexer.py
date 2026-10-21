"""Repo content → files, chunks, embeddings, summaries (Master Doc §11.2–11.3).

All writes go through `ctx.tx()` (fenced), in small batches, so a long index makes
steady progress and a crashed/taken-over worker can't write stale data.
"""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, func, or_, select, update

from docify.ai import prompts
from docify.ai.budget import check_budget, estimate_tokens, record_embedding, record_llm
from docify.ai.chunking import chunk_file, embed_text, search_text
from docify.ai.llm import LLMRefusal, LLMTruncated
from docify.db.models import Chunk, File, Repository
from docify.ingest.filters import language_for
from docify.ingest.redact import redact
from docify.jobs.context import JobContext
from docify.jobs.errors import BudgetExceeded, RetryableError

FILE_BATCH = 40
EMBED_BATCH = 64
SUMMARY_CONCURRENCY = 8
SUMMARY_MAX_CHARS = 24_000  # ~6k tokens of a file is plenty for a 120-word summary
SKIP_SUMMARY_LANGS = {"json", "xml", "text"}


def git_blob_sha(data: bytes) -> str:
    """Same id GitHub uses for blobs, so compare-API `sha` values match ours."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data, usedforsecurity=False).hexdigest()


@dataclass
class SourceFile:
    path: str
    raw: bytes
    text: str  # decoded + redacted

    @property
    def blob_sha(self) -> str:
        return git_blob_sha(self.raw)


def prepare(path: str, raw: bytes, text: str) -> SourceFile:
    redacted, _ = redact(text)
    return SourceFile(path=path, raw=raw, text=redacted)


async def upsert_files(ctx: JobContext, repo: Repository, sha: str, files: Iterable[SourceFile]) -> list[str]:
    """Insert/update files + chunks. Unchanged blobs only get their chunk `commit_sha` bumped.

    Returns paths whose content changed (new or modified).
    """
    changed: list[str] = []
    batch: list[SourceFile] = []

    async def flush() -> None:
        if not batch:
            return
        async with ctx.tx() as db:
            paths = [f.path for f in batch]
            existing = {f.path: f for f in (await db.execute(
                select(File).where(File.repo_id == repo.id, File.path.in_(paths)))).scalars()}
            reuse: dict[str, tuple[Any, str | None]] = {}
            stale_ids = [existing[p].id for p in paths if p in existing]
            if stale_ids:
                # Embeddings of the old chunks, reusable by content hash (moved code keeps its vector).
                for h, emb, model in (await db.execute(
                    select(Chunk.content_hash, Chunk.embedding, Chunk.embed_model)
                    .where(Chunk.file_id.in_(stale_ids), Chunk.embedding.is_not(None))
                )).all():
                    reuse[h] = (emb, model)
            for sf in batch:
                blob = sf.blob_sha
                row = existing.get(sf.path)
                lines = sf.text.count("\n") + 1 if sf.text else 0
                if row is not None and row.blob_sha == blob:
                    await db.execute(update(Chunk).where(Chunk.file_id == row.id).values(commit_sha=sha))
                    continue
                changed.append(sf.path)
                if row is None:
                    row = File(workspace_id=repo.workspace_id, repo_id=repo.id, path=sf.path, blob_sha=blob,
                               language=language_for(sf.path), size=len(sf.raw), line_count=lines)
                    db.add(row)
                    await db.flush()
                else:
                    row.blob_sha, row.size, row.line_count = blob, len(sf.raw), lines
                    row.language = language_for(sf.path)
                    await db.execute(delete(Chunk).where(Chunk.file_id == row.id))
                for piece in chunk_file(sf.path, sf.text):
                    h = piece.content_hash
                    emb, model = reuse.get(h, (None, None))
                    if model != ctx.embedder.model:
                        emb, model = None, None
                    db.add(Chunk(
                        workspace_id=repo.workspace_id, repo_id=repo.id, file_id=row.id, path=sf.path,
                        start_line=piece.start_line, end_line=piece.end_line, commit_sha=sha,
                        content=piece.content, content_hash=h, search_text=search_text(sf.path, piece.content),
                        embedding=emb, embed_model=model,
                    ))
        batch.clear()

    for sf in files:
        batch.append(sf)
        if len(batch) >= FILE_BATCH:
            await flush()
    await flush()
    return changed


async def delete_files(ctx: JobContext, repo: Repository, paths: Iterable[str]) -> None:
    paths = list(paths)
    if not paths:
        return
    async with ctx.tx() as db:
        await db.execute(delete(File).where(File.repo_id == repo.id, File.path.in_(paths)))


async def delete_missing(ctx: JobContext, repo: Repository, keep: set[str]) -> list[str]:
    async with ctx.read() as db:
        current = set((await db.execute(select(File.path).where(File.repo_id == repo.id))).scalars())
    gone = sorted(current - keep)
    for i in range(0, len(gone), 500):
        await delete_files(ctx, repo, gone[i:i + 500])
    return gone


async def embed_missing(ctx: JobContext, repo: Repository) -> int:
    """Embed chunks without a vector for the current model. Provider outage → leave NULL (F22)."""
    total = 0
    model = ctx.embedder.model
    while True:
        async with ctx.read() as db:
            rows = (await db.execute(
                select(Chunk.id, Chunk.path, Chunk.content).where(
                    Chunk.repo_id == repo.id, or_(Chunk.embedding.is_(None), Chunk.embed_model != model))
                .limit(EMBED_BATCH)
            )).all()
            if rows:
                await check_budget(db, repo.workspace_id)
        if not rows:
            return total
        vectors, tokens = await ctx.embedder.embed([embed_text(p, c) for _, p, c in rows], input_type="document")
        async with ctx.tx() as db:
            for (cid, _, _), vec in zip(rows, vectors, strict=True):
                await db.execute(update(Chunk).where(Chunk.id == cid).values(embedding=vec, embed_model=model))
            record_embedding(db, workspace_id=repo.workspace_id, job_id=ctx.job_id, model=model, tokens=tokens)
        total += len(rows)


async def summarise(ctx: JobContext, repo: Repository, *, only_paths: set[str] | None = None) -> int:
    """File summaries (cheap model), cached by blob sha. Runs a few calls concurrently."""
    model = ctx.settings.llm_model_summary
    async with ctx.read() as db:
        q = select(File.id, File.path, File.language).where(
            File.repo_id == repo.id,
            or_(File.summary_blob_sha.is_(None), File.summary_blob_sha != File.blob_sha, File.summary_model != model))
        if only_paths is not None:
            q = q.where(File.path.in_(list(only_paths) or [""]))
        todo = (await db.execute(q.order_by(func.length(File.path), File.path))).all()
    todo = [t for t in todo if t.language and t.language not in SKIP_SUMMARY_LANGS]
    if not todo:
        return 0
    sem = asyncio.Semaphore(SUMMARY_CONCURRENCY)
    done = 0
    budget_hit: BudgetExceeded | None = None

    async def one(file_id: uuid.UUID, path: str) -> None:
        nonlocal done, budget_hit
        async with sem:
            if budget_hit is not None:
                return
            async with ctx.read() as db:
                text_rows = (await db.execute(select(Chunk.start_line, Chunk.content).where(Chunk.file_id == file_id)
                                              .order_by(Chunk.start_line))).all()
                blob = (await db.execute(select(File.blob_sha).where(File.id == file_id))).scalar_one_or_none()
                try:
                    await check_budget(db, repo.workspace_id)
                except BudgetExceeded as exc:
                    budget_hit = exc
                    return
            content = _join_chunks(text_rows)[:SUMMARY_MAX_CHARS]
            tokens = estimate_tokens(content) + 300
            if not ctx.meter.can_spend(tokens):
                return
            ctx.meter.spend(tokens)
            try:
                res = await ctx.llm.complete(
                    task="summary", model=model, system=prompts.SUMMARY_SYSTEM, max_tokens=600,
                    messages=[{"role": "user", "content": f"Path: {path}\n\n<file>\n{content}\n</file>"}],
                    output_schema=prompts.SUMMARY_SCHEMA,
                )
            except (LLMRefusal, LLMTruncated):
                return
            data = res.data or {}
            async with ctx.tx() as db:
                await db.execute(update(File).where(File.id == file_id).values(
                    summary=str(data.get("summary", ""))[:2000],
                    symbols=[str(s)[:200] for s in (data.get("symbols") or [])][:50],
                    summary_model=model, summary_blob_sha=blob))
                record_llm(db, workspace_id=repo.workspace_id, job_id=ctx.job_id, purpose="summary", model=res.model,
                           usage=res.usage)
            done += 1

    results = await asyncio.gather(*(one(fid, path) for fid, path, _ in todo), return_exceptions=True)
    for r in results:
        if isinstance(r, (RetryableError, BudgetExceeded)):
            raise r
        if isinstance(r, BaseException):
            raise r
    if budget_hit is not None:
        raise budget_hit
    return done


def _join_chunks(rows: Any) -> str:
    """Rebuild file text from overlapping chunks."""
    lines: dict[int, str] = {}
    for start, content in rows:
        for i, line in enumerate(content.split("\n")):
            lines.setdefault(start + i, line)
    return "\n".join(lines[k] for k in sorted(lines))


async def file_text(ctx: JobContext, file_id: uuid.UUID) -> str:
    async with ctx.read() as db:
        rows = (await db.execute(select(Chunk.start_line, Chunk.content).where(Chunk.file_id == file_id)
                                 .order_by(Chunk.start_line))).all()
    return _join_chunks(rows)
