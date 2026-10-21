"""installation_sync handler: refresh installation metadata + repo access (Master Doc §8.1, §8.4)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select, update

from docify.db.models import GithubInstallation, Repository
from docify.github.client import GitHubNotFound
from docify.jobs.context import JobContext
from docify.jobs.service import dispatch, enqueue


def _now() -> datetime:
    return datetime.now(UTC)


async def handle_installation_sync(ctx: JobContext) -> None:
    installation_id = int(ctx.payload["installation_id"])
    try:
        meta = await ctx.github.get_installation(installation_id)
    except GitHubNotFound:
        await mark_installation_deleted(ctx, installation_id)
        return
    account = meta.get("account") or {}
    suspended = meta.get("suspended_at")
    async with ctx.tx() as db:
        inst = (await db.execute(select(GithubInstallation).where(
            GithubInstallation.installation_id == installation_id))).scalar_one_or_none()
        if inst is None:
            # Unbound installation (§9.2 step 5): nothing is indexed until a workspace attaches repos.
            inst = GithubInstallation(installation_id=installation_id, account_login=account.get("login", "?"),
                                      account_type=account.get("type", "User"))
            db.add(inst)
        # Only metadata is ever updated here — never ownership (installation hijack defence, F52).
        inst.account_login = account.get("login", inst.account_login)
        inst.account_type = account.get("type", inst.account_type)
        inst.repository_selection = meta.get("repository_selection")
        inst.permissions = meta.get("permissions") or {}
        inst.deleted_at = None
        was_suspended = inst.suspended_at is not None
        inst.suspended_at = _now() if suspended else None

    if suspended:
        async with ctx.tx() as db:
            await db.execute(update(Repository).where(Repository.installation_id == installation_id,
                                                      Repository.status != "disconnected").values(status="suspended"))
        return

    gh = await ctx.github.for_installation(installation_id)
    accessible = {int(r["id"]): r for r in await gh.list_repos()}
    to_dispatch = []
    async with ctx.tx() as db:
        repos = list((await db.execute(select(Repository).where(
            Repository.installation_id == installation_id, Repository.status != "disconnected"))).scalars())
        for repo in repos:
            meta_r = accessible.get(repo.github_repo_id)
            if meta_r is None:
                to_dispatch.append((await enqueue(db, "repo_purge", workspace_id=repo.workspace_id,
                                                  repo_id=repo.id, payload={"reason": "access_removed"})).job_id)
                continue
            repo.full_name, repo.name = meta_r["full_name"], meta_r["name"]
            repo.owner = meta_r["owner"]["login"]
            repo.private, repo.archived = bool(meta_r.get("private")), bool(meta_r.get("archived"))
            if repo.status == "suspended" or was_suspended:
                repo.status = "ready" if repo.last_processed_sha else "pending"
                to_dispatch.append((await enqueue(db, "repo_sync", workspace_id=repo.workspace_id,
                                                  repo_id=repo.id, payload={"reason": "unsuspended"})).job_id)
    await dispatch(to_dispatch)


async def mark_installation_deleted(ctx: JobContext, installation_id: int) -> None:
    to_dispatch = []
    async with ctx.tx() as db:
        await db.execute(update(GithubInstallation).where(GithubInstallation.installation_id == installation_id)
                         .values(deleted_at=_now()))
        repos = (await db.execute(select(Repository).where(Repository.installation_id == installation_id,
                                                           Repository.status != "disconnected"))).scalars().all()
        for repo in repos:
            to_dispatch.append((await enqueue(db, "repo_purge", workspace_id=repo.workspace_id, repo_id=repo.id,
                                              payload={"reason": "uninstalled"})).job_id)
    await dispatch(to_dispatch)
