"""repo_index / repo_sync / repo_purge / reembed handlers (Master Doc §8.1, §9.3, §11)."""

from __future__ import annotations

import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select, update

from docify.ai import docgen, history, indexer
from docify.ai.budget import TokenMeter
from docify.db.models import Document, File, Job, Repository
from docify.github.client import GitHubNotFound, InstallationClient
from docify.github.tarball import iter_tarball
from docify.ingest.filters import content_allowed, load_docifyignore, path_allowed
from docify.jobs.context import JobContext
from docify.jobs.errors import NonRetryableError

INACTIVE = ("disconnected", "suspended")
CONTENTS_API_MAX = 50  # above this, one tarball download is cheaper than N contents calls
BULK_MIN_FILES = 25  # ratio-based "bulk change -> full re-index" only from this many changed files


def _now() -> datetime:
    return datetime.now(UTC)


async def _load_repo(ctx: JobContext) -> Repository | None:
    async with ctx.read() as db:
        return await db.get(Repository, ctx.repo_id)


async def _set_repo(ctx: JobContext, repo: Repository, **values: Any) -> None:
    async with ctx.tx() as db:
        stmt = update(Repository).where(Repository.id == repo.id)
        if "status" in values:  # never resurrect a repo removed/suspended while we were working
            stmt = stmt.where(Repository.status.not_in(INACTIVE))
        await db.execute(stmt.values(**values))
    for k, v in values.items():
        setattr(repo, k, v)


async def _refresh_metadata(ctx: JobContext, gh: InstallationClient, repo: Repository) -> dict[str, Any]:
    try:
        meta = await gh.get_repo(repo.full_name, repo.github_repo_id)
    except GitHubNotFound as exc:
        raise NonRetryableError("Repository no longer accessible.", code="repo_gone",
                                repo_status="disconnected") from exc
    owner = meta["owner"]["login"]
    await _set_repo(ctx, repo, full_name=meta["full_name"], owner=owner, name=meta["name"],
                    default_branch=meta.get("default_branch") or repo.default_branch,
                    private=bool(meta.get("private")), archived=bool(meta.get("archived")),
                    size_kb=int(meta.get("size") or 0),
                    github_created_at=history.parse_ts(meta.get("created_at")))
    return meta


async def handle_repo_index(ctx: JobContext) -> None:
    repo = await _load_repo(ctx)
    if repo is None or repo.status in INACTIVE:
        return
    gh = await ctx.github.for_installation(repo.installation_id)
    await _refresh_metadata(ctx, gh, repo)
    if repo.size_kb and repo.size_kb > ctx.settings.repo_max_mb * 1024 * 2:  # GitHub `size` ≈ packed size
        raise NonRetryableError("Repository is too large for Docify.", code="too_large", repo_status="too_large")
    head = await gh.branch_head(repo.full_name, repo.default_branch)
    if head is None:
        await _set_repo(ctx, repo, status="empty", last_synced_at=_now(), error=None)
        return
    await _set_repo(ctx, repo, status="indexing", error=None)
    await full_index(ctx, gh, repo, head)


async def full_index(ctx: JobContext, gh: InstallationClient, repo: Repository, head: str) -> None:
    s = ctx.settings
    with tempfile.TemporaryDirectory(prefix="docify-") as tmp:
        archive = Path(tmp) / "repo.tar.gz"
        await gh.download_tarball(repo.full_name, head, archive, max_bytes=s.repo_max_mb * 1024 * 1024)
        await ctx.storage.put_file(f"repos/{repo.id}/{head}.tar.gz", archive)
        ignore_text = next((f.data.decode("utf-8", "replace") for f in
                            iter_tarball(archive, max_file_bytes=64 * 1024, wanted={".docifyignore"})), None)
        ignore = load_docifyignore(ignore_text)
        max_bytes = s.file_max_kb * 1024
        candidates = 0
        keep: set[str] = set()

        def files() -> Any:
            nonlocal candidates
            for tf in iter_tarball(archive, max_file_bytes=max_bytes):
                if not path_allowed(tf.path, ignore) or not tf.data:
                    continue
                text_ = content_allowed(tf.data, max_bytes)
                if text_ is None:
                    continue
                candidates += 1
                if candidates > s.repo_max_files:
                    raise NonRetryableError(f"Repository has more than {s.repo_max_files} indexable files.",
                                            code="too_large", repo_status="too_large")
                keep.add(tf.path)
                yield indexer.prepare(tf.path, tf.data, text_)

        ctx.meter = TokenMeter(limit=2_000 * s.repo_max_files + 200_000)
        await indexer.upsert_files(ctx, repo, head, files())
        ctx.meter = TokenMeter(limit=2_000 * max(candidates, 1) + 200_000)
        await indexer.delete_missing(ctx, repo, keep)
    await indexer.embed_missing(ctx, repo)
    await indexer.summarise(ctx, repo)
    for kind in docgen.DOC_KINDS:
        await docgen.generate_doc(ctx, repo, kind, head)
    await history.record_commits(ctx, gh, repo, head)
    await _set_repo(ctx, repo, status="ready", last_processed_sha=head, last_full_index_sha=head,
                    indexed_branch=repo.default_branch, last_synced_at=_now(), error=None)


async def handle_repo_sync(ctx: JobContext) -> None:
    repo = await _load_repo(ctx)
    if repo is None or repo.status in INACTIVE:
        return
    if repo.status != "ready" or not repo.last_processed_sha:
        await handle_repo_index(ctx)
        return
    gh = await ctx.github.for_installation(repo.installation_id)
    await _refresh_metadata(ctx, gh, repo)
    if repo.archived:
        return  # F12: archived repos stop syncing, docs are kept
    if repo.default_branch != repo.indexed_branch:
        await handle_repo_index(ctx)
        return
    head = await gh.branch_head(repo.full_name, repo.default_branch)
    if head is None:
        await _set_repo(ctx, repo, status="empty", last_synced_at=_now())
        return
    if head == repo.last_processed_sha:
        await history.record_commits(ctx, gh, repo, head, listed=[])  # backfills repos indexed before D63
        await _set_repo(ctx, repo, last_synced_at=_now())
        return
    cmp = await gh.compare(repo.full_name, repo.last_processed_sha, head)
    files_changed: list[dict[str, Any]] = (cmp or {}).get("files") or []
    async with ctx.read() as db:
        total_files = len((await db.execute(select(File.path).where(File.repo_id == repo.id))).all())
    # Upgrade to a full re-index for history rewrites and bulk changes. The ratio rule only applies to
    # real bulk changes (>= BULK_MIN_FILES): in a 5-file repo any normal PR touches > 20 % of the files,
    # and that used to skip the incremental path - and with it the changelog (found 2026-11-01).
    bulk = len(files_changed) >= BULK_MIN_FILES and total_files and len(files_changed) > 0.2 * total_files
    if cmp is None or cmp.get("status") not in ("ahead", "identical") or len(files_changed) >= 300 or bulk:
        ctx.log.info("sync.upgrade_to_index", status=(cmp or {}).get("status"), files=len(files_changed))
        previous_sha = repo.last_processed_sha
        await _set_repo(ctx, repo, status="indexing")
        await full_index(ctx, gh, repo, head)
        commits = (cmp or {}).get("commits") or []
        if cmp is not None and cmp.get("status") == "ahead" and commits:
            # Still record what changed: a full re-index must not make pushes vanish from the changelog.
            changed = sorted({f["filename"] for f in files_changed}
                             | {f["previous_filename"] for f in files_changed if f.get("previous_filename")})
            await docgen.write_changelog(ctx, repo, from_sha=previous_sha, to_sha=head, commits=commits,
                                         changed=changed)
        return
    await incremental(ctx, gh, repo, head, cmp, files_changed)


async def incremental(ctx: JobContext, gh: InstallationClient, repo: Repository, head: str, cmp: dict[str, Any],
                      files_changed: list[dict[str, Any]]) -> None:
    s = ctx.settings
    if any(f.get("filename") == ".docifyignore" or f.get("previous_filename") == ".docifyignore"
           for f in files_changed):
        await _set_repo(ctx, repo, status="indexing")
        await full_index(ctx, gh, repo, head)
        return
    removed = {f["filename"] for f in files_changed if f.get("status") == "removed"}
    removed |= {f["previous_filename"] for f in files_changed if f.get("status") == "renamed"
                and f.get("previous_filename")}
    wanted = {f["filename"] for f in files_changed if f.get("status") != "removed"}
    async with ctx.read() as db:
        ignore_row = (await db.execute(select(File.id).where(File.repo_id == repo.id,
                                                             File.path == ".docifyignore"))).scalar_one_or_none()
    ignore = load_docifyignore((await indexer.file_text(ctx, ignore_row)) if ignore_row else None)
    wanted = {p for p in wanted if path_allowed(p, ignore)}
    max_bytes = s.file_max_kb * 1024
    sources: list[indexer.SourceFile] = []
    if len(wanted) > CONTENTS_API_MAX:
        with tempfile.TemporaryDirectory(prefix="docify-") as tmp:
            archive = Path(tmp) / "repo.tar.gz"
            await gh.download_tarball(repo.full_name, head, archive, max_bytes=s.repo_max_mb * 1024 * 1024)
            for tf in iter_tarball(archive, max_file_bytes=max_bytes, wanted=wanted):
                text_ = content_allowed(tf.data, max_bytes) if tf.data else None
                if text_ is not None:
                    sources.append(indexer.prepare(tf.path, tf.data, text_))
    else:
        for path in sorted(wanted):
            data = await gh.get_file(repo.full_name, path, head)
            text_ = content_allowed(data, max_bytes) if data else None
            if text_ is not None:
                sources.append(indexer.prepare(path, data or b"", text_))
    # Files that became binary/too big/ignored are dropped like removals.
    dropped = wanted - {sf.path for sf in sources}
    await indexer.delete_files(ctx, repo, sorted(removed | dropped))
    ctx.meter = TokenMeter(limit=300_000)
    changed = await indexer.upsert_files(ctx, repo, head, sources)
    await indexer.embed_missing(ctx, repo)
    await indexer.summarise(ctx, repo, only_paths=set(changed))

    added_or_removed = {f["filename"] for f in files_changed if f.get("status") in ("added", "removed", "renamed")}
    async with ctx.read() as db:
        docs = {d.kind: list(d.source_paths or []) for d in
                (await db.execute(select(Document).where(Document.repo_id == repo.id))).scalars()}
    route_files = set(await docgen._route_files(ctx, repo.id))
    route_files |= removed & set(docs.get("api", []))  # a removed route file only shows up in old sources
    kinds = docgen.docs_to_update(set(changed) | removed, added_or_removed, docs, route_files)
    note = "Changed files:\n" + "\n".join(
        f"- {f.get('status')}: {f['filename']}" + (f" (was {f['previous_filename']})" if f.get("previous_filename")
                                                     else "") for f in files_changed[:200])
    for kind in kinds:
        await docgen.generate_doc(ctx, repo, kind, head, change_note=note if kind in docs else None)
    commits = cmp.get("commits") or []
    await history.record_commits(ctx, gh, repo, head, listed=commits)
    if commits or changed or removed:
        await docgen.write_changelog(ctx, repo, from_sha=repo.last_processed_sha, to_sha=head, commits=commits,
                                     changed=sorted(set(changed) | removed))
    await _set_repo(ctx, repo, last_processed_sha=head, last_synced_at=_now(), error=None)


async def handle_repo_purge(ctx: JobContext) -> None:
    """Delete everything we stored for a repo (F10). Idempotent."""
    async with ctx.read() as db:
        repo = await db.get(Repository, ctx.repo_id) if ctx.repo_id else None
    if repo is None:
        return
    async with ctx.tx() as db:
        await db.execute(update(Repository).where(Repository.id == repo.id).values(status="disconnected"))
        # Cancel queued work for this repo; handlers also no-op on disconnected repos.
        await db.execute(update(Job).where(Job.dedupe_key == f"repo:{repo.id}", Job.status.in_(
            ("queued", "blocked_budget"))).values(status="succeeded", finished_at=_now(),
                                                  error={"cancelled": "repo purged"}))
    await ctx.storage.delete_prefix(f"repos/{repo.id}/")
    async with ctx.tx() as db:
        # Children cascade (files → chunks, documents → versions, changelog).
        await db.execute(delete(Repository).where(Repository.id == repo.id))


async def handle_reembed(ctx: JobContext) -> None:
    repo = await _load_repo(ctx)
    if repo is None or repo.status in INACTIVE:
        return
    await indexer.embed_missing(ctx, repo)
