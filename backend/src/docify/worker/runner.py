"""Process one SQS message end to end (Master Doc §5.3, §8.3).

Message kinds:
- `github_event`: dedupe + create/coalesce jobs in one transaction, then notify.
- `job`: claim → repo lease → run handler with heartbeats → finish / retry / dead.
- `loadtest`: simulated work (P11), only when LOADTEST_MESSAGES=true.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any

from sqlalchemy import select

from docify.ai.embeddings import get_embedder
from docify.ai.llm import get_llm
from docify.config import get_settings
from docify.db.models import Job, Repository
from docify.db.session import session_factory, session_scope
from docify.github.client import GitHubApp
from docify.jobs import service
from docify.jobs.context import JobContext
from docify.jobs.errors import BudgetExceeded, LeaseLost, NonRetryableError, RetryableError
from docify.jobs.events import handle_event
from docify.jobs.handlers.installation import handle_installation_sync
from docify.jobs.handlers.repo import handle_reembed, handle_repo_index, handle_repo_purge, handle_repo_sync
from docify.jobs.queue import QueueMessage, SqsQueue
from docify.observability.logging import get_logger
from docify.observability.metrics import JOB_DURATION, JOBS
from docify.storage.backend import get_storage

log = get_logger("docify.worker")

Handler = Callable[[JobContext], Awaitable[None]]
HANDLERS: dict[str, Handler] = {
    "repo_index": handle_repo_index,
    "repo_sync": handle_repo_sync,
    "repo_purge": handle_repo_purge,
    "installation_sync": handle_installation_sync,
    "reembed": handle_reembed,
}
HEARTBEAT_S = 60
VISIBILITY_S = 300
LOADTEST_MAX_MS = 30_000



class Runner:
    def __init__(self, queue: SqsQueue, github: GitHubApp | None = None) -> None:
        self.queue = queue
        self.settings = get_settings()
        self.github = github or GitHubApp()

    async def process(self, msg: QueueMessage) -> None:
        kind = msg.body.get("kind")
        if kind == "github_event":
            await self._process_event(msg)
        elif kind == "job" and msg.body.get("job_id"):
            await self._process_job(msg)
        elif kind == "loadtest" and self.settings.loadtest_messages:
            await self._process_loadtest(msg)
        else:
            log.warning("worker.unknown_message", kind=kind)
            await self.queue.delete(msg.receipt)

    # ------------------------------------------------------------------ events

    async def _process_event(self, msg: QueueMessage) -> None:
        async with session_scope() as db:
            job_ids = await handle_event(db, msg.body)
        await service.dispatch(job_ids)
        await self.queue.delete(msg.receipt)

    async def _process_loadtest(self, msg: QueueMessage) -> None:
        """P11 burst generator: simulated work so KEDA can be shown scaling 0 -> max -> 0 at zero AI cost."""
        try:
            work_ms = max(0, min(int(msg.body.get("work_ms", 2000)), LOADTEST_MAX_MS))
        except (TypeError, ValueError):
            work_ms = 2000
        started = time.monotonic()
        await asyncio.sleep(work_ms / 1000)
        JOB_DURATION.labels("loadtest").observe(time.monotonic() - started)
        JOBS.labels("loadtest", "succeeded").inc()
        await self.queue.delete(msg.receipt)

    # ------------------------------------------------------------------ jobs

    async def _process_job(self, msg: QueueMessage) -> None:
        try:
            job_id = uuid.UUID(str(msg.body["job_id"]))
        except ValueError:
            await self.queue.delete(msg.receipt)
            return
        token = service.worker_token()
        async with session_scope() as db:
            claimed = await service.claim(db, job_id, token)
            if claimed is None:
                await self._unclaimable(db, job_id, msg)
                return
        await self._run_claimed(claimed, token, msg)

    async def _unclaimable(self, db: Any, job_id: uuid.UUID, msg: QueueMessage) -> None:
        """Rule 1, "no row" branch."""
        job = await db.get(Job, job_id)
        if job is not None and job.status == "queued":
            if job.attempts >= job.max_attempts:
                await service.finish(db, job, "dead", error={"message": "attempts exhausted"})
            else:
                wait = (job.run_after - service.utcnow()).total_seconds()
                if wait > 0:
                    await db.commit()
                    await self.queue.send(msg.body, delay_s=int(wait) + 1)
        elif job is not None and job.status == "running" and job.attempts >= job.max_attempts \
                and job.lease_expires_at and job.lease_expires_at < service.utcnow():
            await service.finish(db, job, "dead", error={"message": "attempts exhausted"})
        await self.queue.delete(msg.receipt)

    async def _run_claimed(self, c: service.Claimed, token: str, msg: QueueMessage) -> None:
        holds_repo = False
        if c.repo_id is not None and c.type in service.REPO_JOB_TYPES:
            async with session_scope() as db:
                exists = await db.get(Repository, c.repo_id)
                if exists is None:
                    holds_repo = False  # repo gone (purged); handler will no-op
                elif not await service.acquire_repo_lease(db, c.repo_id, token):
                    # Repo busy → back to queued without burning an attempt (rule 2).
                    job = await service.load_job_locked(db, c.job_id, c.fence, token)
                    open_id = await service.requeue(db, job, run_after=service.utcnow() +
                                                    timedelta(seconds=service.REPO_BUSY_DELAY_S))
                    await db.commit()
                    await service.dispatch([open_id], delay_s=service.REPO_BUSY_DELAY_S)
                    await self.queue.delete(msg.receipt)
                    return
                else:
                    holds_repo = True
        async with session_scope() as db:
            attempt = await service.mark_started(db, c.job_id, c.fence, token)

        ctx = JobContext(
            job_id=c.job_id, job_type=c.type, fence=c.fence, worker=token, workspace_id=c.workspace_id,
            repo_id=c.repo_id, payload=c.payload, attempt=attempt, settings=self.settings, github=self.github,
            llm=get_llm(), embedder=get_embedder(), storage=get_storage(), holds_repo_lease=holds_repo,
        )
        started = time.monotonic()
        stop_heartbeat = asyncio.Event()
        lease_lost = asyncio.Event()  # set by the heartbeat when another worker took over
        task = asyncio.create_task(self._run_handler(ctx))
        hb = asyncio.create_task(self._heartbeat(ctx, msg, stop_heartbeat, lease_lost, task))
        outcome: str
        try:
            await task
            outcome = "succeeded"
        except asyncio.CancelledError:
            me = asyncio.current_task()
            if me is not None and me.cancelling():
                # Worker shutdown (SIGTERM after the drain window): hand the job back quickly (§5.3).
                stop_heartbeat.set()
                hb.cancel()
                await self._shutdown_requeue(ctx, msg)
                raise
            outcome = "lease_lost"  # the heartbeat cancelled the handler
        except Exception as exc:
            outcome = await self._on_error(ctx, exc, msg)
        finally:
            stop_heartbeat.set()
            hb.cancel()
            with contextlib.suppress(BaseException):
                await hb
        JOB_DURATION.labels(c.type).observe(time.monotonic() - started)

        if outcome == "succeeded":
            async with session_scope() as db:
                try:
                    job = await service.load_job_locked(db, c.job_id, c.fence, token)
                except LeaseLost:
                    outcome = "lease_lost"
                else:
                    await service.finish(db, job, "succeeded")
                    if holds_repo and c.repo_id:
                        await service.release_repo_lease(db, c.repo_id, token)
            JOBS.labels(c.type, outcome).inc()
            log.info("job.done", job_id=str(c.job_id), type=c.type, outcome=outcome)
        elif holds_repo and c.repo_id and outcome != "lease_lost":
            async with session_scope() as db:
                await service.release_repo_lease(db, c.repo_id, token)
        await self.queue.delete(msg.receipt)

    async def _run_handler(self, ctx: JobContext) -> None:
        timeout = service.TIMEOUTS_S.get(ctx.job_type, service.DEFAULT_TIMEOUT_S)
        async with asyncio.timeout(timeout):
            await HANDLERS[ctx.job_type](ctx)

    async def _heartbeat(self, ctx: JobContext, msg: QueueMessage, stop: asyncio.Event, lost: asyncio.Event,
                         task: asyncio.Task[None]) -> None:
        while not stop.is_set():
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=HEARTBEAT_S)
            if stop.is_set():
                return
            try:
                async with session_scope() as db:
                    ok = await service.heartbeat(db, ctx.job_id, ctx.fence, ctx.worker,
                                                 ctx.repo_id if ctx.holds_repo_lease else None)
                await self.queue.change_visibility(msg.receipt, VISIBILITY_S)
            except Exception as exc:  # transient DB/SQS blip: try again next beat
                log.warning("job.heartbeat_failed", error=type(exc).__name__)
                continue
            if not ok:
                log.warning("job.lease_lost", job_id=str(ctx.job_id))
                lost.set()
                task.cancel()
                return

    async def _on_error(self, ctx: JobContext, exc: Exception, msg: QueueMessage) -> str:
        c = ctx
        if isinstance(exc, LeaseLost):
            log.warning("job.lease_lost", job_id=str(c.job_id))
            return "lease_lost"
        try:
            async with session_scope() as db:
                job = await service.load_job_locked(db, c.job_id, c.fence, c.worker)
                if isinstance(exc, BudgetExceeded):
                    job.attempts = max(0, job.attempts - 1)  # waiting for budget is not a failed attempt
                    open_id = await service.requeue(db, job, run_after=service.utcnow(),
                                                    error={"message": str(exc), "code": "budget"},
                                                    status="blocked_budget")
                    outcome = "blocked_budget"
                    log.info("job.blocked_budget", job_id=str(c.job_id), open_id=str(open_id))
                elif isinstance(exc, NonRetryableError):
                    await service.finish(db, job, "failed", error={"message": str(exc), "code": exc.code})
                    purge_id = await self._repo_error(db, c, exc)
                    outcome = "failed"
                    if purge_id is not None:
                        await db.commit()
                        await service.dispatch([purge_id])
                else:
                    retryable = isinstance(exc, (RetryableError, TimeoutError, ConnectionError, OSError))
                    if not retryable:
                        log.exception("job.crashed", job_id=str(c.job_id), error=type(exc).__name__)
                    err = {"message": str(exc)[:500] or type(exc).__name__, "type": type(exc).__name__}
                    if job.attempts >= job.max_attempts:
                        await service.finish(db, job, "dead", error=err)
                        await self._repo_error(db, c, NonRetryableError(
                            "Processing failed repeatedly. An admin can retry it from the Jobs page.", code="dead"))
                        outcome = "dead"
                    else:
                        delay = getattr(exc, "delay_s", None) or service.backoff_s(job.attempts)
                        open_id = await service.requeue(
                            db, job, run_after=service.utcnow() + timedelta(seconds=delay),
                            error=err)
                        await db.commit()
                        # Delete + re-send with delay resets the SQS receive count (rule 9).
                        await service.dispatch([open_id], delay_s=delay)
                        outcome = "retry"
        except LeaseLost:
            return "lease_lost"
        JOBS.labels(c.job_type, outcome).inc()
        log.info("job.done", job_id=str(c.job_id), type=c.job_type, outcome=outcome, error=type(exc).__name__)
        return outcome

    async def _repo_error(self, db: Any, ctx: JobContext, exc: NonRetryableError) -> uuid.UUID | None:
        """Record a permanent failure on the repo. Lost access → queue a purge (F10); returns its job id."""
        if ctx.repo_id is None or ctx.job_type == "repo_purge":
            return None
        repo = (await db.execute(select(Repository).where(Repository.id == ctx.repo_id).with_for_update())) \
            .scalar_one_or_none()
        if repo is None or repo.status == "disconnected":
            return None
        repo.status = exc.repo_status or ("error" if repo.status in ("pending", "indexing") else repo.status)
        repo.error = {"message": str(exc), "code": exc.code}
        if repo.status == "disconnected":
            return (await service.enqueue(db, "repo_purge", workspace_id=repo.workspace_id, repo_id=repo.id,
                                          payload={"reason": exc.code})).job_id
        return None

    async def _shutdown_requeue(self, ctx: JobContext, msg: QueueMessage) -> None:
        try:
            async with session_factory()() as db:
                job = await service.load_job_locked(db, ctx.job_id, ctx.fence, ctx.worker)
                job.attempts = max(0, job.attempts - 1)  # interrupted by us, not a real failure
                open_id = await service.requeue(db, job, run_after=service.utcnow())
                if ctx.holds_repo_lease and ctx.repo_id:
                    await service.release_repo_lease(db, ctx.repo_id, ctx.worker)
                await db.commit()
            await self.queue.change_visibility(msg.receipt, 0)
            if open_id != ctx.job_id:
                await self.queue.delete(msg.receipt)
        except Exception as exc:
            log.warning("job.shutdown_requeue_failed", error=type(exc).__name__)
