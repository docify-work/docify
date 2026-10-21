"""`docify <command>` entry point (Master Doc §5.2). One image, many roles."""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from importlib import resources
from typing import Any

from docify.config import get_settings
from docify.observability.logging import configure_logging, get_logger

log = get_logger("docify.cli")


def _setup(service: str) -> None:
    s = get_settings()
    configure_logging(level=s.log_level, json=s.log_json, service=service, env=s.env, version=s.version)


def cmd_api(args: argparse.Namespace) -> None:
    import uvicorn

    from docify.observability.metrics import start_metrics_server

    s = get_settings()
    if not args.reload:
        start_metrics_server(s.metrics_port)
    uvicorn.run("docify.api.app:create_app", factory=True, host=args.host, port=args.port, reload=args.reload,
                proxy_headers=False, access_log=False, log_config=None, timeout_graceful_shutdown=20)


def cmd_worker(args: argparse.Namespace) -> None:
    from docify.db.session import dispose_engine, init_engine
    from docify.observability.metrics import start_metrics_server
    from docify.worker.loop import run_worker

    _setup("worker")
    s = get_settings()
    s.check_deployable()
    start_metrics_server(s.metrics_port)

    async def main() -> None:
        init_engine(pool_size=3)
        try:
            await run_worker(once=args.once)
        finally:
            await dispose_engine()

    asyncio.run(main())


def alembic_config(url: str | None = None) -> Any:
    from alembic.config import Config

    cfg = Config()
    cfg.set_main_option("script_location", str(resources.files("docify.db").joinpath("migrations")))
    if url:
        cfg.attributes["database_url"] = url
    return cfg


def cmd_migrate(args: argparse.Namespace) -> None:
    """Retries the DB connection for up to 5 minutes (Argo hook may start before Postgres is ready)."""
    from alembic import command

    _setup("migrate")
    deadline = time.monotonic() + args.wait
    while True:
        try:
            asyncio.run(_ping())
            break
        except Exception as exc:
            if time.monotonic() > deadline:
                log.error("migrate.db_unreachable", error=type(exc).__name__)
                sys.exit(1)
            log.info("migrate.waiting_for_db", error=type(exc).__name__)
            time.sleep(5)
    command.upgrade(alembic_config(), "head")
    log.info("migrate.done")


async def _ping() -> None:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(get_settings().database_url)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    finally:
        await engine.dispose()


def _run_async(coro_factory: Any, service: str, pool: int = 2) -> Any:
    from docify.db.session import dispose_engine, init_engine

    _setup(service)

    async def main() -> object:
        init_engine(pool_size=pool)
        try:
            return await coro_factory()
        finally:
            await dispose_engine()

    return asyncio.run(main())


def cmd_reconcile(_: argparse.Namespace) -> None:
    from docify.jobs.reconcile import reconcile_once

    print(_run_async(reconcile_once, "reconcile"))


def cmd_housekeeping(_: argparse.Namespace) -> None:
    from docify.jobs.housekeeping import housekeeping

    print(_run_async(housekeeping, "housekeeping"))


def cmd_seed_demo(args: argparse.Namespace) -> None:
    from docify.demo.seed import seed_demo

    print(_run_async(lambda: seed_demo(admin_email=args.admin_email, from_dir=args.from_dir,
                                       github_repo=args.github_repo, installation_id=args.installation_id),
                     "seed-demo", pool=4))


def cmd_verify_db(_: argparse.Namespace) -> None:
    from docify.demo.verify import verify_db

    ok = _run_async(verify_db, "verify-db")
    sys.exit(0 if ok else 1)


def cmd_eval(args: argparse.Namespace) -> None:
    from docify.demo.evaluate import run_eval

    ok = _run_async(lambda: run_eval(args.questions, args.workspace, args.min_hit), "eval", pool=2)
    sys.exit(0 if ok else 1)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="docify", description="Docify backend")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("api", help="run the HTTP API (port 8000) + metrics (9000)")
    a.add_argument("--host", default="0.0.0.0")  # noqa: S104 - container
    a.add_argument("--port", type=int, default=8000)
    a.add_argument("--reload", action="store_true")
    a.set_defaults(fn=cmd_api)

    w = sub.add_parser("worker", help="run the SQS worker")
    w.add_argument("--once", action="store_true", help="exit when the queue is empty (tests/demos)")
    w.set_defaults(fn=cmd_worker)

    m = sub.add_parser("migrate", help="alembic upgrade head (waits for the DB)")
    m.add_argument("--wait", type=int, default=300)
    m.set_defaults(fn=cmd_migrate)

    sub.add_parser("reconcile", help="one reconcile pass").set_defaults(fn=cmd_reconcile)
    sub.add_parser("housekeeping", help="purge old rows").set_defaults(fn=cmd_housekeeping)

    sd = sub.add_parser("seed-demo", help="create/refresh the public Demo workspace")
    sd.add_argument("--admin-email", help="make this existing user an admin of the demo workspace")
    sd.add_argument("--from-dir", help="index a local folder as the demo repo (no GitHub needed)")
    sd.add_argument("--github-repo", help="owner/name of a public repo to attach (needs --installation-id)")
    sd.add_argument("--installation-id", type=int)
    sd.set_defaults(fn=cmd_seed_demo)

    sub.add_parser("verify-db", help="sanity checks after a restore").set_defaults(fn=cmd_verify_db)

    e = sub.add_parser("eval", help="retrieval eval (§11.7)")
    e.add_argument("--questions", default=None, help="path to questions.yaml (default: bundled)")
    e.add_argument("--workspace", default=None, help="workspace slug (default: demo)")
    e.add_argument("--min-hit", type=float, default=0.8)
    e.set_defaults(fn=cmd_eval)

    args = p.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
