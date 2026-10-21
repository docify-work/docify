"""`docify verify-db`: quick sanity checks after a restore (runbook R7)."""

from __future__ import annotations

from sqlalchemy import text

from docify.db.session import session_scope

TABLES = ("users", "workspaces", "repositories", "files", "chunks", "documents", "document_versions", "jobs")


async def verify_db() -> bool:
    from alembic.script import ScriptDirectory

    from docify.cli import alembic_config

    head = ScriptDirectory.from_config(alembic_config()).get_current_head()
    ok = True
    async with session_scope() as db:
        current = (await db.execute(text("SELECT version_num FROM alembic_version"))).scalar_one_or_none()
        print(f"alembic: current={current} head={head} {'OK' if current == head else 'MISMATCH'}")
        ok &= current == head
        for t in TABLES:
            n = (await db.execute(text(f"SELECT count(*) FROM {t}"))).scalar_one()  # noqa: S608 - fixed names
            print(f"{t:<20} {n}")
        ext = set((await db.execute(text("SELECT extname FROM pg_extension"))).scalars())
        missing = {"vector", "pg_trgm", "citext"} - ext
        print(f"extensions: {'OK' if not missing else 'MISSING ' + ', '.join(sorted(missing))}")
        ok &= not missing
    return bool(ok)
