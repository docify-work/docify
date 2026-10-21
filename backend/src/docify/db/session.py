"""Async engine + session factory.

Pool sizes are small on purpose (Master Doc §5.5 connection budget): api 5, worker 3,
`max_overflow=0` so a burst can't exhaust Postgres' 80 connections.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from docify.config import get_settings

_engine: AsyncEngine | None = None
_factory: async_sessionmaker[AsyncSession] | None = None


def init_engine(url: str | None = None, *, pool_size: int | None = None) -> AsyncEngine:
    global _engine, _factory
    settings = get_settings()
    _engine = create_async_engine(
        url or settings.database_url,
        pool_size=pool_size or settings.db_pool_size,
        max_overflow=0,
        pool_pre_ping=True,
        pool_recycle=1800,
        connect_args={"server_settings": {"application_name": f"docify-{settings.env}"}},
    )
    _factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_engine() -> AsyncEngine:
    if _engine is None:
        init_engine()
    assert _engine is not None
    return _engine


def session_factory() -> async_sessionmaker[AsyncSession]:
    if _factory is None:
        init_engine()
    assert _factory is not None
    return _factory


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """A session that commits on success and rolls back on error."""
    async with session_factory()() as session:
        try:
            yield session
            await session.commit()
        except BaseException:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    global _engine, _factory
    if _engine is not None:
        await _engine.dispose()
    _engine, _factory = None, None
