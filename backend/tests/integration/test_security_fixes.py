"""Regression tests for the 2026-10-21 review findings (one test per fix)."""

from __future__ import annotations

import uuid
from urllib.parse import parse_qs, urlparse

import httpx
from sqlalchemy import select

from docify.api.app import create_app
from docify.db.models import Job, Repository, User
from docify.db.session import session_scope
from docify.email.sender import MemorySender
from tests.helpers.github import FakeGitHub
from tests.integration.conftest import TOKEN_RE, make_user, make_workspace

PW_ATTACKER = "attacker pass 12345"
PW_VICTIM = "victim pass 67890 x"


def new_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(start_background=False)),
                             base_url="http://testserver", headers={"X-Docify-CSRF": "1"})


async def test_unverified_signup_takeover_blocked(outbox: MemorySender) -> None:
    """#1: attacker registers victim's email; victim later signs up and verifies → attacker's password is gone."""
    attacker, victim = new_client(), new_client()
    await attacker.post("/api/auth/signup", json={"email": "vic@example.com", "password": PW_ATTACKER})
    await victim.post("/api/auth/signup", json={"email": "vic@example.com", "password": PW_VICTIM})
    token = TOKEN_RE.search(outbox.outbox[-1].text).group(1)  # type: ignore[union-attr]
    assert (await victim.post("/api/auth/verify-email", json={"token": token})).status_code == 200
    r = await attacker.post("/api/auth/login", json={"email": "vic@example.com", "password": PW_ATTACKER})
    assert r.status_code == 401
    r = await victim.post("/api/auth/login", json={"email": "vic@example.com", "password": PW_VICTIM})
    assert r.status_code == 200


async def test_resend_verification_wipes_unknown_password(outbox: MemorySender) -> None:
    attacker, victim = new_client(), new_client()
    await attacker.post("/api/auth/signup", json={"email": "v2@example.com", "password": PW_ATTACKER})
    await victim.post("/api/auth/resend-verification", json={"email": "v2@example.com"})
    token = TOKEN_RE.search(outbox.outbox[-1].text).group(1)  # type: ignore[union-attr]
    assert (await victim.post("/api/auth/verify-email", json={"token": token})).status_code == 200
    async with session_scope() as db:
        user = (await db.execute(select(User).where(User.email == "v2@example.com"))).scalar_one()
        assert user.password_hash is None  # the stranger's password did not survive
    assert (await victim.get("/api/me")).json()["has_password"] is False


async def test_oauth_callback_from_another_browser_rejected(gh: FakeGitHub) -> None:
    """#2: login CSRF — the attacker's half-finished flow can't be completed in the victim's browser."""
    attacker, victim = new_client(), new_client()
    r = await attacker.get("/api/auth/github/start")
    state = parse_qs(urlparse(r.headers["location"]).query)["state"][0]
    r = await victim.get(f"/api/auth/github/callback?code=attacker-code&state={state}")
    assert "error=oauth_state" in r.headers["location"]
    assert (await victim.get("/api/me")).status_code == 401


async def test_install_limits_attach_to_repos_user_can_see(outbox: MemorySender, gh: FakeGitHub) -> None:
    """#3: org member without access to the repo can't list or attach it."""
    gh.user_sees_repo = False
    c = await make_user(outbox, "member@example.com")
    ws = await make_workspace(c, "Org")
    r = await c.get(f"/api/workspaces/{ws['slug']}/github/install-url")
    state = parse_qs(urlparse(r.json()["url"]).query)["state"][0]
    r = await c.get(f"/api/github/setup?installation_id={gh.installation_id}&setup_action=install&state={state}")
    oauth_state = parse_qs(urlparse(r.headers["location"]).query)["state"][0]
    r = await c.get(f"/api/auth/github/callback?code=x&state={oauth_state}")
    assert r.headers["location"].endswith("?connected=1")
    insts = (await c.get(f"/api/workspaces/{ws['slug']}/github/installations")).json()
    assert insts[0]["repos"] == []
    r = await c.post(f"/api/workspaces/{ws['slug']}/github/installations/{gh.installation_id}/repos",
                     json={"github_repo_ids": [gh.repo_id]})
    assert r.status_code == 404


async def test_client_ip_prefers_cloudfront_viewer_address() -> None:
    """#4: X-Forwarded-For's first entry is client-controlled; CloudFront-Viewer-Address isn't."""
    from starlette.requests import Request

    from docify.api.deps import client_ip
    from docify.config import get_settings

    scope = {"type": "http", "headers": [(b"x-forwarded-for", b"6.6.6.6, 1.2.3.4"),
                                         (b"cloudfront-viewer-address", b"203.0.113.9:51234")],
             "client": ("10.0.0.1", 1)}
    assert client_ip(Request(scope)) == "203.0.113.9"
    s = get_settings()
    old = s.env
    s.env = "prod"
    try:
        scope["headers"] = [(b"x-forwarded-for", b"6.6.6.6")]
        assert client_ip(Request(scope)) == "10.0.0.1"  # never trust XFF in the cloud
    finally:
        s.env = old


async def test_lost_access_queues_purge(outbox: MemorySender, gh: FakeGitHub) -> None:
    """#5: repo marked disconnected by a failed job gets a purge job (not stuck forever)."""
    from tests.integration.test_pipeline import drain, setup_repo

    _, ws, repo_id = await setup_repo(outbox, gh)
    gh.mock.get(f"https://api.github.com/repos/{gh.full_name}").mock(return_value=httpx.Response(404))
    gh.mock.get(f"https://api.github.com/repositories/{gh.repo_id}").mock(return_value=httpx.Response(404))
    async with session_scope() as db:
        from docify.jobs import service

        job = await service.enqueue(db, "repo_sync", workspace_id=uuid.UUID(ws["id"]), repo_id=repo_id)
    await service.dispatch([job.job_id])
    await drain()
    async with session_scope() as db:
        assert await db.get(Repository, repo_id) is None  # purged
        types = (await db.execute(select(Job.type, Job.status).where(Job.type == "repo_purge"))).all()
        assert ("repo_purge", "succeeded") in types


async def test_budget_block_does_not_burn_attempts(outbox: MemorySender, gh: FakeGitHub) -> None:
    """#7: waiting for budget never exhausts attempts."""
    from docify.config import get_settings
    from tests.integration.test_pipeline import setup_repo

    s = get_settings()
    old = s.ai_daily_budget_usd
    s.ai_daily_budget_usd = 0.0
    try:
        _, _, repo_id = await setup_repo(outbox, gh)
    finally:
        s.ai_daily_budget_usd = old
    async with session_scope() as db:
        job = (await db.execute(select(Job).where(Job.repo_id == repo_id))).scalar_one()
    assert job.status == "blocked_budget"
    assert job.attempts == 0


async def test_logout_everywhere_else(client: httpx.AsyncClient, outbox: MemorySender) -> None:
    c1 = await make_user(outbox, "lo@example.com")
    await client.post("/api/auth/login", json={"email": "lo@example.com", "password": "correct horse battery 9"})
    assert (await c1.post("/api/me/sessions/revoke-others")).status_code == 200
    assert (await client.get("/api/me")).status_code == 401
    assert (await c1.get("/api/me")).status_code == 200
