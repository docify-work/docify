"""Job state machine rules (§8.3): coalescing, claim/recovery, leases, fencing, merge-on-requeue, events."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from sqlalchemy import func, select, text

from docify.db.models import Job, Repository, WebhookDelivery, Workspace
from docify.db.session import session_scope
from docify.jobs import service
from docify.jobs.errors import LeaseLost
from docify.jobs.events import handle_event


async def _repo() -> tuple[uuid.UUID, uuid.UUID]:
    async with session_scope() as db:
        ws = Workspace(slug=f"ws-{uuid.uuid4().hex[:6]}", name="W")
        db.add(ws)
        await db.flush()
        repo = Repository(workspace_id=ws.id, installation_id=99, github_repo_id=555, owner="acme", name="taskly",
                          full_name="acme/taskly", default_branch="main", status="ready", last_processed_sha="a" * 40)
        db.add(repo)
        await db.flush()
        return ws.id, repo.id


async def test_coalescing_one_open_job_per_repo() -> None:
    ws, repo = await _repo()
    async with session_scope() as db:
        ids = {(await service.enqueue(db, "repo_sync", workspace_id=ws, repo_id=repo)).job_id for _ in range(20)}
        upgraded = await service.enqueue(db, "repo_index", workspace_id=ws, repo_id=repo, payload={"reason": "force"})
    assert ids == {upgraded.job_id}
    async with session_scope() as db:
        job = await db.get(Job, upgraded.job_id)
        assert job is not None
        assert job.type == "repo_index"  # a sync is upgraded, never downgraded
        assert (await db.execute(select(func.count()).select_from(Job))).scalar_one() == 1
        # A later sync stays an index.
        again = await service.enqueue(db, "repo_sync", workspace_id=ws, repo_id=repo)
        assert again.job_id == job.id
        await db.refresh(job)
        assert job.type == "repo_index"


async def test_running_plus_one_queued() -> None:
    ws, repo = await _repo()
    async with session_scope() as db:
        first = (await service.enqueue(db, "repo_sync", workspace_id=ws, repo_id=repo)).job_id
        assert await service.claim(db, first, "w1") is not None
        second = (await service.enqueue(db, "repo_sync", workspace_id=ws, repo_id=repo)).job_id
        third = (await service.enqueue(db, "repo_sync", workspace_id=ws, repo_id=repo)).job_id
    assert first != second == third


async def test_claim_is_exclusive_and_recovers_after_crash() -> None:
    ws, repo = await _repo()
    async with session_scope() as db:
        jid = (await service.enqueue(db, "repo_sync", workspace_id=ws, repo_id=repo)).job_id
        c1 = await service.claim(db, jid, "w1")
        assert c1 is not None
        assert await service.claim(db, jid, "w2") is None  # lease still valid
        # Simulate crash: lease expires.
        await db.execute(text("UPDATE jobs SET lease_expires_at = now() - interval '1 second' WHERE id = :i"), {"i": jid})
        c2 = await service.claim(db, jid, "w2")
        assert c2 is not None
        assert c2.fence == c1.fence + 1
    # Old worker's writes are fenced off.
    async with session_scope() as db:
        with pytest.raises(LeaseLost):
            await service.check_fence(db, jid, c1.fence, "w1")
        await service.check_fence(db, jid, c2.fence, "w2")


async def test_future_run_after_not_claimable() -> None:
    ws, repo = await _repo()
    async with session_scope() as db:
        jid = (await service.enqueue(db, "repo_sync", workspace_id=ws, repo_id=repo,
                                     run_after=service.utcnow() + timedelta(minutes=5))).job_id
        assert await service.claim(db, jid, "w1") is None


async def test_attempts_exhausted_not_claimable() -> None:
    ws, repo = await _repo()
    async with session_scope() as db:
        jid = (await service.enqueue(db, "repo_sync", workspace_id=ws, repo_id=repo)).job_id
        await db.execute(text("UPDATE jobs SET attempts = max_attempts WHERE id = :i"), {"i": jid})
        assert await service.claim(db, jid, "w1") is None


async def test_repo_lease_mutual_exclusion() -> None:
    _, repo = await _repo()
    async with session_scope() as db:
        assert await service.acquire_repo_lease(db, repo, "w1")
        assert not await service.acquire_repo_lease(db, repo, "w2")
        await service.release_repo_lease(db, repo, "w1")
        assert await service.acquire_repo_lease(db, repo, "w2")
        await db.execute(text("UPDATE repositories SET sync_lease_expires_at = now() - interval '1s'"))
        assert await service.acquire_repo_lease(db, repo, "w3")  # expired lease can be taken


async def test_requeue_merges_into_open_twin() -> None:
    ws, repo = await _repo()
    async with session_scope() as db:
        running = (await service.enqueue(db, "repo_index", workspace_id=ws, repo_id=repo)).job_id
        c = await service.claim(db, running, "w1")
        assert c is not None
        twin = (await service.enqueue(db, "repo_sync", workspace_id=ws, repo_id=repo)).job_id
        job = await service.load_job_locked(db, running, c.fence, "w1")
        open_id = await service.requeue(db, job, run_after=service.utcnow())
        assert open_id == twin
        await db.flush()
        twin_job = await db.get(Job, twin)
        assert twin_job is not None
        assert twin_job.type == "repo_index"  # merged type keeps the stronger job
        assert job.status == "succeeded"
        assert job.error == {"coalesced_into": str(twin)}


async def test_singleton_lease() -> None:
    async with session_scope() as db:
        assert await service.acquire_singleton(db, "reconciler", "a", timedelta(minutes=10))
        assert not await service.acquire_singleton(db, "reconciler", "b", timedelta(minutes=10))
        await service.release_singleton(db, "reconciler", "a")
        assert await service.acquire_singleton(db, "reconciler", "b", timedelta(minutes=10))


async def test_event_dedupe_and_push_jobs() -> None:
    _ws, repo = await _repo()
    push = {"v": 1, "kind": "github_event", "delivery_id": "d-1", "event": "push", "installation_id": 99,
            "repo_id": 555, "after": "b" * 40, "forced": False}
    async with session_scope() as db:
        assert len(await handle_event(db, push)) == 1
    async with session_scope() as db:
        assert await handle_event(db, push) == []  # replayed delivery → nothing new (F3)
    async with session_scope() as db:
        jobs = await handle_event(db, {**push, "delivery_id": "d-2", "forced": True})
        job = await db.get(Job, jobs[0])
        assert job is not None
        assert job.type == "repo_index"  # force push upgrades the queued sync (F6)
        assert (await db.execute(select(func.count()).select_from(WebhookDelivery))).scalar_one() == 2
        assert (await db.execute(select(func.count()).select_from(Job))).scalar_one() == 1
    # Unknown repo: ignored but recorded.
    async with session_scope() as db:
        assert await handle_event(db, {**push, "delivery_id": "d-3", "repo_id": 1}) == []
    del repo


async def test_uninstall_event_purges_repos() -> None:
    await _repo()
    async with session_scope() as db:
        ids = await handle_event(db, {"v": 1, "kind": "github_event", "delivery_id": "u1", "event": "installation",
                                      "action": "deleted", "installation_id": 99})
        assert len(ids) == 1
        assert (await db.get(Job, ids[0])).type == "repo_purge"  # type: ignore[union-attr]


async def test_rename_event_updates_identity_by_id() -> None:
    _, repo = await _repo()
    async with session_scope() as db:
        await handle_event(db, {"v": 1, "kind": "github_event", "delivery_id": "r1", "event": "repository",
                                "action": "renamed", "repo_id": 555, "full_name": "acme/taskly-v2"})
    async with session_scope() as db:
        r = await db.get(Repository, repo)
        assert r is not None
        assert (r.full_name, r.name) == ("acme/taskly-v2", "taskly-v2")
