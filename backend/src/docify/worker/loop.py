"""Worker main loop (Master Doc §5.3).

- Long-polls SQS, asking only for as many messages as there are free slots.
- Touches a heartbeat file every iteration (Kubernetes liveness probe checks its age).
- SIGTERM: stop receiving, let in-flight jobs finish for up to 120 s, then hand
  the rest back (job → queued, message visible again).
"""

from __future__ import annotations

import asyncio
import contextlib
import signal
from pathlib import Path

from docify.config import get_settings
from docify.jobs.queue import get_queue
from docify.jobs.reconcile import reconcile_once
from docify.observability.logging import get_logger
from docify.observability.metrics import WORKER_BUSY
from docify.worker.runner import Runner

log = get_logger("docify.worker")
DRAIN_S = 120


def touch(path: str) -> None:
    with contextlib.suppress(OSError):
        Path(path).touch()


async def run_worker(*, once: bool = False) -> None:
    s = get_settings()
    queue = get_queue()
    runner = Runner(queue)
    stopping = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        with contextlib.suppress(NotImplementedError):  # Windows dev
            loop.add_signal_handler(sig, stopping.set)

    inflight: set[asyncio.Task[None]] = set()
    concurrency = max(1, s.worker_concurrency)
    log.info("worker.start", concurrency=concurrency)

    # Reconcile at startup (catches anything missed while asleep, F1/F2).
    try:
        await reconcile_once()
    except Exception as exc:
        log.warning("worker.startup_reconcile_failed", error=type(exc).__name__)

    async def handle(msg: object) -> None:
        try:
            await runner.process(msg)  # type: ignore[arg-type]
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # Message stays invisible until its timeout → redelivered; DLQ after 5 receives (rule 10).
            log.exception("worker.message_failed", error=type(exc).__name__)

    while not stopping.is_set():
        touch(s.worker_heartbeat_file)
        free = concurrency - len(inflight)
        if free <= 0:
            done, _ = await asyncio.wait(inflight, timeout=20, return_when=asyncio.FIRST_COMPLETED)
            inflight.difference_update(done)
            WORKER_BUSY.set(len(inflight))
            continue
        receive = asyncio.create_task(queue.receive(free, wait_s=1 if once else 20))
        stop_wait = asyncio.create_task(stopping.wait())
        await asyncio.wait({receive, stop_wait}, return_when=asyncio.FIRST_COMPLETED)
        stop_wait.cancel()
        if not receive.done():
            receive.cancel()
            with contextlib.suppress(BaseException):
                await receive
            break
        try:
            messages = receive.result()
        except Exception as exc:
            log.warning("worker.receive_failed", error=type(exc).__name__)
            await asyncio.sleep(5)
            continue
        for msg in messages:
            t = asyncio.create_task(handle(msg))
            inflight.add(t)
            t.add_done_callback(inflight.discard)
        WORKER_BUSY.set(len(inflight))
        if once and not messages and not inflight:
            break

    if inflight:
        log.info("worker.draining", inflight=len(inflight))
        _, pending = await asyncio.wait(inflight, timeout=DRAIN_S)
        for t in pending:
            t.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
    log.info("worker.stopped")
