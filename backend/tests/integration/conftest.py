from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass

import httpx
import pytest
import respx
from sqlalchemy import text

from docify.ai.embeddings import set_embedder
from docify.ai.fakes import FakeEmbedder, FakeLLM
from docify.ai.llm import set_llm
from docify.api.app import create_app
from docify.cache import close_valkey, get_valkey
from docify.db.session import dispose_engine, init_engine, session_scope
from docify.email.sender import MemorySender, set_email_sender
from docify.jobs.queue import get_queue
from tests.helpers.github import FakeGitHub

TABLES = ("audit_events", "chat_messages", "chat_threads", "llm_usage", "singletons", "webhook_deliveries", "jobs",
          "changelog_entries", "documents", "document_versions", "chunks", "files", "repositories",
          "workspace_installations", "github_installations", "invites", "memberships", "oauth_states",
          "email_tokens", "sessions", "auth_identities", "workspaces", "users")


@pytest.fixture(scope="session", autouse=True)
async def migrated() -> AsyncIterator[None]:
    from alembic import command

    from docify.cli import alembic_config

    await asyncio.to_thread(command.upgrade, alembic_config(), "head")
    return


@pytest.fixture(autouse=True)
async def clean(migrated: None) -> AsyncIterator[None]:
    init_engine(pool_size=5)
    async with session_scope() as db:
        await db.execute(text(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE"))
    await get_valkey().flushdb()
    await get_queue().purge()
    set_llm(FakeLLM())
    set_embedder(FakeEmbedder())
    yield
    await close_valkey()
    await dispose_engine()


@pytest.fixture
def outbox() -> Iterator[MemorySender]:
    sender = MemorySender()
    set_email_sender(sender)
    yield sender
    set_email_sender(None)


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(start_background=False)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver",
                                 headers={"X-Docify-CSRF": "1"}) as c:
        yield c


@pytest.fixture
def anon(client: httpx.AsyncClient) -> httpx.AsyncClient:
    return client


@pytest.fixture
def gh() -> Iterator[FakeGitHub]:
    with respx.mock(assert_all_called=False) as mock:
        yield FakeGitHub(mock)


TOKEN_RE = re.compile(r"token=([A-Za-z0-9_\-]+)")


@dataclass
class TestUser:
    email: str
    client: httpx.AsyncClient


async def make_user(outbox: MemorySender, email: str, password: str = "correct horse battery 9") -> httpx.AsyncClient:
    """Sign up + verify via the real API; returns a logged-in client (own cookie jar)."""
    app = create_app(start_background=False)
    c = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver",
                          headers={"X-Docify-CSRF": "1"})
    r = await c.post("/api/auth/signup", json={"email": email, "password": password, "name": email.split("@")[0]})
    assert r.status_code == 202, r.text
    mail = next(m for m in reversed(outbox.outbox) if m.to == email and "Verify" in m.subject)
    token = TOKEN_RE.search(mail.text).group(1)  # type: ignore[union-attr]
    r = await c.post("/api/auth/verify-email", json={"token": token})
    assert r.status_code == 200, r.text
    return c


async def make_workspace(c: httpx.AsyncClient, name: str = "Acme Team") -> dict:  # type: ignore[type-arg]
    r = await c.post("/api/workspaces", json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]
