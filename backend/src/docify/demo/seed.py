"""`docify seed-demo`: create/refresh the public Demo workspace (Master Doc §2.4, P5.7/P9.6).

Two sources:
- `--github-repo owner/name --installation-id N`: attach a real public repo; the worker indexes it.
- `--from-dir PATH`: index a local folder directly (local dev / CI demo, no GitHub needed).
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

from sqlalchemy import select, update

from docify.ai import docgen, indexer
from docify.ai.budget import TokenMeter
from docify.ai.embeddings import get_embedder
from docify.ai.llm import get_llm
from docify.config import get_settings
from docify.db.models import Membership, Repository, User, Workspace, WorkspaceInstallation
from docify.db.session import session_scope
from docify.github.client import GitHubApp
from docify.ingest.filters import content_allowed, path_allowed
from docify.jobs import service
from docify.jobs.context import JobContext
from docify.storage.backend import get_storage


async def _demo_workspace() -> Workspace:
    s = get_settings()
    async with session_scope() as db:
        ws = (await db.execute(select(Workspace).where(Workspace.slug == s.demo_workspace_slug))).scalar_one_or_none()
        if ws is None:
            ws = Workspace(slug=s.demo_workspace_slug, name="Docify Demo", is_public_demo=True,
                           settings={"auto_publish": True, "chat_enabled": True})
            db.add(ws)
            await db.flush()
        ws.is_public_demo = True
        ws.deleted_at = None
        await db.flush()
        db.expunge(ws)
        return ws


async def seed_demo(*, admin_email: str | None, from_dir: str | None, github_repo: str | None,
                    installation_id: int | None) -> dict[str, Any]:
    ws = await _demo_workspace()
    result: dict[str, Any] = {"workspace": ws.slug}
    if admin_email:
        async with session_scope() as db:
            user = (await db.execute(select(User).where(User.email == admin_email.lower()))).scalar_one_or_none()
            if user is None:
                raise SystemExit(f"No user with email {admin_email}; sign up first.")
            m = (await db.execute(select(Membership).where(Membership.workspace_id == ws.id,
                                                           Membership.user_id == user.id))).scalar_one_or_none()
            if m is None:
                db.add(Membership(workspace_id=ws.id, user_id=user.id, role="admin"))
            else:
                m.role = "admin"
        result["admin"] = admin_email
    if github_repo:
        result["github"] = await _attach_github(ws, github_repo, installation_id)
    if from_dir:
        result["local"] = await _index_dir(ws, Path(from_dir))
    return result


async def _attach_github(ws: Workspace, full_name: str, installation_id: int | None) -> str:
    if not installation_id:
        raise SystemExit("--installation-id is required with --github-repo")
    app = GitHubApp()
    try:
        client = await app.for_installation(installation_id)
        meta = next((r for r in await client.list_repos() if r["full_name"].lower() == full_name.lower()), None)
    finally:
        await app.aclose()
    if meta is None:
        raise SystemExit(f"{full_name} is not accessible to installation {installation_id}")
    if meta.get("private"):
        raise SystemExit("The demo workspace must only contain public repositories (F13).")
    async with session_scope() as db:
        if (await db.execute(select(WorkspaceInstallation).where(
                WorkspaceInstallation.workspace_id == ws.id,
                WorkspaceInstallation.installation_id == installation_id))).scalar_one_or_none() is None:
            db.add(WorkspaceInstallation(workspace_id=ws.id, installation_id=installation_id))
        repo = (await db.execute(select(Repository).where(Repository.github_repo_id == int(meta["id"]))))\
            .scalar_one_or_none()
        if repo is None:
            repo = Repository(workspace_id=ws.id, installation_id=installation_id, github_repo_id=int(meta["id"]),
                              owner=meta["owner"]["login"], name=meta["name"], full_name=meta["full_name"],
                              default_branch=meta.get("default_branch") or "main", status="pending")
            db.add(repo)
            await db.flush()
        elif repo.workspace_id != ws.id:
            raise SystemExit("That repo is already attached to another workspace.")
        job = await service.enqueue(db, "repo_index", workspace_id=ws.id, repo_id=repo.id, payload={"reason": "seed"})
    await service.dispatch([job.job_id])
    return f"queued repo_index for {full_name}"


def _walk(root: Path) -> list[tuple[str, bytes]]:
    out = []
    max_bytes = get_settings().file_max_kb * 1024
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith(".git"))
        for name in sorted(filenames):
            full = Path(dirpath) / name
            rel = full.relative_to(root).as_posix()
            if not path_allowed(rel):
                continue
            data = full.read_bytes()
            if content_allowed(data, max_bytes) is not None:
                out.append((rel, data))
    return out


async def _index_dir(ws: Workspace, root: Path) -> str:
    if not root.is_dir():
        raise SystemExit(f"{root} is not a directory")
    files = _walk(root)
    sha = hashlib.sha1(b"".join(p.encode() + d for p, d in files), usedforsecurity=False).hexdigest()
    name = root.resolve().name
    synthetic_id = -int(hashlib.sha1(f"demo:{name}".encode(), usedforsecurity=False).hexdigest()[:12], 16)
    async with session_scope() as db:
        repo = (await db.execute(select(Repository).where(Repository.github_repo_id == synthetic_id)))\
            .scalar_one_or_none()
        if repo is None:
            repo = Repository(workspace_id=ws.id, installation_id=0, github_repo_id=synthetic_id, owner="docify-demo",
                              name=name, full_name=f"docify-demo/{name}", default_branch="main", status="indexing")
            db.add(repo)
            await db.flush()
        repo_id = repo.id
        job = await service.enqueue(db, "repo_index", workspace_id=ws.id, repo_id=repo_id,
                                    payload={"reason": "seed_local"})
    token = service.worker_token()
    async with session_scope() as db:
        claimed = await service.claim(db, job.job_id, token)
        assert claimed is not None, "could not claim seed job"
        assert await service.acquire_repo_lease(db, repo_id, token)
        await service.mark_started(db, claimed.job_id, claimed.fence, token)
    ctx = JobContext(job_id=claimed.job_id, job_type="repo_index", fence=claimed.fence, worker=token,
                     workspace_id=ws.id, repo_id=repo_id, payload={}, attempt=1, settings=get_settings(),
                     github=GitHubApp(), llm=get_llm(), embedder=get_embedder(), storage=get_storage(),
                     meter=TokenMeter(limit=2_000 * len(files) + 200_000), holds_repo_lease=True)
    async with ctx.read() as db:
        repo = await db.get(Repository, repo_id)
        assert repo is not None
    await indexer.upsert_files(ctx, repo, sha, (indexer.prepare(p, d, d.decode("utf-8")) for p, d in files))
    await indexer.delete_missing(ctx, repo, {p for p, _ in files})
    await indexer.embed_missing(ctx, repo)
    await indexer.summarise(ctx, repo)
    for kind in docgen.DOC_KINDS:
        await docgen.generate_doc(ctx, repo, kind, sha)
    async with session_scope() as db:
        await db.execute(update(Repository).where(Repository.id == repo_id).values(
            status="ready", last_processed_sha=sha, last_full_index_sha=sha, indexed_branch="main",
            last_synced_at=service.utcnow()))
        job_row = await service.load_job_locked(db, claimed.job_id, claimed.fence, token)
        await service.finish(db, job_row, "succeeded")
        await service.release_repo_lease(db, repo_id, token)
    await ctx.github.aclose()
    return f"indexed {len(files)} files from {root} as docify-demo/{name}"
