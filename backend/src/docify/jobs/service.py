"""Job state machine in Postgres (Master Doc §8.2–8.3).

Why this design:
- SQS only *notifies*; Postgres is the truth (status, attempts, leases).
- Row leases + a monotonically increasing `fence` replace advisory locks (D32):
  a worker that lost its lease can never commit writes, because every write
  re-checks `(fence, lease_owner)` in the same transaction.
- `dedupe_key` + a partial unique index coalesce bursts: at most one queued and one
  running job per repo, no matter how many pushes arrive.
"""

from __future__ import annotations

import os
import random
import socket
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from docify.db.models import Job, Repository
from docify.jobs.errors import LeaseLost
from docify.jobs.queue import get_queue, job_message
from docify.observability.logging import get_logger

log = get_logger(__name__)

LEASE = timedelta(minutes=5)
REPO_BUSY_DELAY_S = 60
OPEN_STATUSES = ("queued", "blocked_budget")
REPO_JOB_TYPES = ("repo_index", "repo_sync", "repo_purge", "reembed")
TIMEOUTS_S = {"repo_index": 30 * 60, "repo_sync": 10 * 60}
DEFAULT_TIMEOUT_S = 5 * 60


def worker_token() -> str:
    """Unique per job execution, so two slots in one process never share a lease."""
    return f"{socket.gethostname()[:40]}:{os.getpid()}:{uuid.uuid4().hex[:8]}"


def utcnow() -> datetime:
    return datetime.now(UTC)


def backoff_s(attempts: int) -> int:
    """min(30·2^attempts, 900) seconds ±20% jitter (rule 9)."""
    base = min(30 * (2 ** max(0, attempts)), 900)
    return max(1, int(base * random.uniform(0.8, 1.2)))


def dedupe_key_for(job_type: str, *, repo_id: uuid.UUID | None = None,
                   installation_id: int | None = None) -> str | None:
    if job_type in ("repo_index", "repo_sync"):
        return f"repo:{repo_id}"
    if job_type == "repo_purge":
        return f"purge:{repo_id}"
    if job_type == "reembed":
        return f"reembed:{repo_id}"
    if job_type == "installation_sync":
        return f"inst:{installation_id}"
    return None


# The ON CONFLICT predicate must match the partial index predicate exactly (rule 5).
_ENQUEUE_SQL = text("""
INSERT INTO jobs (workspace_id, repo_id, type, dedupe_key, payload, run_after)
VALUES (:workspace_id, :repo_id, :type, :dedupe_key, CAST(:payload AS jsonb),
        COALESCE(CAST(:run_after AS timestamptz), now()))
ON CONFLICT (dedupe_key) WHERE status IN ('queued', 'blocked_budget')
DO UPDATE SET
  type = CASE WHEN 'repo_index' IN (jobs.type, EXCLUDED.type) THEN 'repo_index' ELSE jobs.type END,
  run_after = LEAST(jobs.run_after, EXCLUDED.run_after),
  payload = jobs.payload || EXCLUDED.payload,
  updated_at = now()
RETURNING id, (xmax = 0) AS inserted
""")


@dataclass
class Enqueued:
    job_id: uuid.UUID
    inserted: bool


async def enqueue(db: AsyncSession, job_type: str, *, workspace_id: uuid.UUID | None,
                  repo_id: uuid.UUID | None = None, installation_id: int | None = None,
                  payload: dict[str, Any] | None = None, run_after: datetime | None = None) -> Enqueued:
    """Create or coalesce a job. Caller must COMMIT, then `dispatch()` the returned ids."""
    import json

    key = dedupe_key_for(job_type, repo_id=repo_id, installation_id=installation_id)
    pl = dict(payload or {})
    if installation_id is not None:
        pl.setdefault("installation_id", installation_id)
    row = (await db.execute(_ENQUEUE_SQL, {
        "workspace_id": workspace_id, "repo_id": repo_id, "type": job_type, "dedupe_key": key,
        "payload": json.dumps(pl), "run_after": run_after,  # None → DB now() (same clock as claim)
    })).one()
    return Enqueued(row.id, bool(row.inserted))


async def dispatch(job_ids: Iterable[uuid.UUID], *, delay_s: int = 0) -> None:
    """Send notification messages. Safe to call twice: claims are idempotent (rule 1).

    If this fails after commit, the reconciler re-sends stale queued jobs (rule 7, outbox gap).
    """
    queue = get_queue()
    for job_id in dict.fromkeys(job_ids):
        try:
            await queue.send(job_message(str(job_id)), delay_s=delay_s)
        except Exception as exc:  # pragma: no cover - logged, reconciler covers it
            log.warning("jobs.dispatch_failed", job_id=str(job_id), error=type(exc).__name__)


# ----------------------------------------------------------------------------- claim


_CLAIM_SQL = text("""
UPDATE jobs SET status = 'running', lease_owner = :worker, lease_expires_at = now() + interval '5 minutes',
       fence = fence + 1, updated_at = now()
WHERE id = :id AND attempts < max_attempts
  AND ((status = 'queued' AND run_after <= now())
       OR (status = 'running' AND lease_expires_at < now()))
RETURNING id, fence, type, repo_id, workspace_id, attempts, max_attempts, payload
""")


@dataclass
class Claimed:
    job_id: uuid.UUID
    fence: int
    type: str
    repo_id: uuid.UUID | None
    workspace_id: uuid.UUID | None
    attempts: int
    max_attempts: int
    payload: dict[str, Any]


async def claim(db: AsyncSession, job_id: uuid.UUID, worker: str) -> Claimed | None:
    row = (await db.execute(_CLAIM_SQL, {"id": job_id, "worker": worker})).first()
    if row is None:
        return None
    return Claimed(row.id, row.fence, row.type, row.repo_id, row.workspace_id, row.attempts, row.max_attempts,
                   dict(row.payload or {}))


async def acquire_repo_lease(db: AsyncSession, repo_id: uuid.UUID, worker: str) -> bool:
    row = (await db.execute(
        update(Repository)
        .where(Repository.id == repo_id, or_(Repository.sync_lease_owner.is_(None),
                                             Repository.sync_lease_expires_at < text("now()"),
                                             Repository.sync_lease_owner == worker))
        .values(sync_lease_owner=worker, sync_lease_expires_at=text("now() + interval '5 minutes'"))
        .returning(Repository.id)
    )).first()
    return row is not None


async def release_repo_lease(db: AsyncSession, repo_id: uuid.UUID, worker: str) -> None:
    await db.execute(update(Repository).where(Repository.id == repo_id, Repository.sync_lease_owner == worker)
                     .values(sync_lease_owner=None, sync_lease_expires_at=None))


async def check_fence(db: AsyncSession, job_id: uuid.UUID, fence: int, worker: str,
                      repo_id: uuid.UUID | None = None) -> None:
    """Call inside every write transaction of a handler (rule 4). Row lock orders us vs. a takeover."""
    ok = (await db.execute(text(
        "SELECT 1 FROM jobs WHERE id = :id AND fence = :fence AND lease_owner = :w AND status = 'running' FOR UPDATE"
    ), {"id": job_id, "fence": fence, "w": worker})).first()
    if ok is None:
        raise LeaseLost(f"job {job_id} lease lost")
    if repo_id is not None:
        repo_ok = (await db.execute(text(
            "SELECT 1 FROM repositories WHERE id = :id AND sync_lease_owner = :w FOR UPDATE"
        ), {"id": repo_id, "w": worker})).first()
        if repo_ok is None:
            raise LeaseLost(f"repo {repo_id} lease lost")


async def heartbeat(db: AsyncSession, job_id: uuid.UUID, fence: int, worker: str,
                    repo_id: uuid.UUID | None) -> bool:
    res = await db.execute(text(
        "UPDATE jobs SET lease_expires_at = now() + interval '5 minutes' "
        "WHERE id = :id AND fence = :fence AND lease_owner = :w AND status = 'running' RETURNING id"
    ), {"id": job_id, "fence": fence, "w": worker})
    if res.first() is None:
        return False
    if repo_id is not None:
        await db.execute(text(
            "UPDATE repositories SET sync_lease_expires_at = now() + interval '5 minutes' "
            "WHERE id = :id AND sync_lease_owner = :w"
        ), {"id": repo_id, "w": worker})
    return True


async def mark_started(db: AsyncSession, job_id: uuid.UUID, fence: int, worker: str) -> int:
    """Attempts only count once real work starts (rule 3). Returns the new attempt number."""
    row = (await db.execute(text(
        "UPDATE jobs SET attempts = attempts + 1, started_at = now(), error = NULL "
        "WHERE id = :id AND fence = :fence AND lease_owner = :w RETURNING attempts"
    ), {"id": job_id, "fence": fence, "w": worker})).first()
    if row is None:
        raise LeaseLost(f"job {job_id} lease lost")
    return int(row.attempts)


# ----------------------------------------------------------------------------- finish / requeue


def _merge_payload(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    return {**a, **b}


async def requeue(db: AsyncSession, job: Job, *, run_after: datetime, error: dict[str, Any] | None = None,
                  status: str = "queued") -> uuid.UUID:
    """Return a running job to `queued`/`blocked_budget`, merging into an open twin if one exists (rule 5a).

    Returns the id of the job that is now open (this one or the twin).
    """
    twin: Job | None = None
    if job.dedupe_key:
        twin = (await db.execute(
            select(Job).where(Job.dedupe_key == job.dedupe_key, Job.status.in_(OPEN_STATUSES), Job.id != job.id)
            .with_for_update()
        )).scalar_one_or_none()
    if twin is not None:
        if "repo_index" in (twin.type, job.type):
            twin.type = "repo_index"
        twin.run_after = min(twin.run_after, run_after)
        twin.payload = _merge_payload(job.payload or {}, twin.payload or {})
        job.status = "succeeded"
        job.error = {"coalesced_into": str(twin.id)}
        job.finished_at = utcnow()
        job.lease_owner = None
        job.lease_expires_at = None
        return twin.id
    job.status = status
    job.run_after = run_after
    job.lease_owner = None
    job.lease_expires_at = None
    if error is not None:
        job.error = error
    return job.id


async def finish(db: AsyncSession, job: Job, status: str, *, error: dict[str, Any] | None = None) -> None:
    job.status = status
    job.finished_at = utcnow()
    job.lease_owner = None
    job.lease_expires_at = None
    if error is not None:
        job.error = error


async def load_job_locked(db: AsyncSession, job_id: uuid.UUID, fence: int, worker: str) -> Job:
    job = (await db.execute(
        select(Job).where(Job.id == job_id, Job.fence == fence, Job.lease_owner == worker).with_for_update()
    )).scalar_one_or_none()
    if job is None:
        raise LeaseLost(f"job {job_id} lease lost")
    return job


async def retry_job(db: AsyncSession, job: Job) -> uuid.UUID | None:
    """Admin retry for failed/dead jobs. Returns the open job id (maybe a merged twin)."""
    if job.status not in ("failed", "dead"):
        return None
    job.attempts = 0
    return await requeue(db, job, run_after=utcnow(), error=None)


# ----------------------------------------------------------------------------- reconciler helpers


async def expired_running(db: AsyncSession, limit: int = 100) -> list[Job]:
    return list((await db.execute(
        select(Job).where(Job.status == "running", Job.lease_expires_at < text("now()"))
        .order_by(Job.lease_expires_at).limit(limit).with_for_update(skip_locked=True)
    )).scalars())


async def stale_queued_ids(db: AsyncSession, older_than: timedelta = timedelta(minutes=5),
                           limit: int = 200) -> list[uuid.UUID]:
    return list((await db.execute(
        select(Job.id).where(Job.status == "queued", Job.run_after < utcnow() - older_than)
        .order_by(Job.run_after).limit(limit)
    )).scalars())


async def clear_expired_repo_leases(db: AsyncSession) -> None:
    await db.execute(update(Repository).where(and_(Repository.sync_lease_owner.is_not(None),
                                                    Repository.sync_lease_expires_at < text("now()")))
                     .values(sync_lease_owner=None, sync_lease_expires_at=None))


# ----------------------------------------------------------------------------- singletons


async def acquire_singleton(db: AsyncSession, name: str, owner: str, ttl: timedelta) -> bool:
    row = (await db.execute(text("""
        INSERT INTO singletons (name, owner, expires_at) VALUES (:n, :o, now() + :ttl)
        ON CONFLICT (name) DO UPDATE SET owner = EXCLUDED.owner, expires_at = EXCLUDED.expires_at
        WHERE singletons.expires_at <= now() OR singletons.owner = EXCLUDED.owner
        RETURNING name
    """), {"n": name, "o": owner, "ttl": ttl})).first()
    return row is not None


async def release_singleton(db: AsyncSession, name: str, owner: str) -> None:
    await db.execute(text("UPDATE singletons SET expires_at = now() - interval '1 second' WHERE name = :n AND owner = :o"),
                     {"n": name, "o": owner})
