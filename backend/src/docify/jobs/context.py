"""Everything a job handler needs, plus fenced transactions (rule 4)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from docify.ai.budget import TokenMeter
from docify.ai.embeddings import Embedder
from docify.ai.llm import LLM
from docify.config import Settings
from docify.db.session import session_factory
from docify.github.client import GitHubApp
from docify.jobs.service import check_fence
from docify.observability.logging import get_logger
from docify.storage.backend import Storage


@dataclass
class JobContext:
    job_id: uuid.UUID
    job_type: str
    fence: int
    worker: str
    workspace_id: uuid.UUID | None
    repo_id: uuid.UUID | None
    payload: dict[str, Any]
    attempt: int
    settings: Settings
    github: GitHubApp
    llm: LLM
    embedder: Embedder
    storage: Storage
    meter: TokenMeter = field(default_factory=lambda: TokenMeter(limit=300_000))
    holds_repo_lease: bool = False

    @property
    def log(self) -> Any:
        return get_logger("docify.job").bind(job_id=str(self.job_id), job_type=self.job_type,
                                              repo_id=str(self.repo_id) if self.repo_id else None)

    @asynccontextmanager
    async def tx(self) -> AsyncIterator[AsyncSession]:
        """A transaction that first proves we still own the job (and repo) lease."""
        async with session_factory()() as db:
            try:
                await check_fence(db, self.job_id, self.fence, self.worker,
                                  self.repo_id if self.holds_repo_lease else None)
                yield db
                await db.commit()
            except BaseException:
                await db.rollback()
                raise

    @asynccontextmanager
    async def read(self) -> AsyncIterator[AsyncSession]:
        """Read-only session (no fence needed)."""
        async with session_factory()() as db:
            yield db
