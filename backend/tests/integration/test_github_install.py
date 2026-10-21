"""GitHub install + attach flow (§9.2) incl. installation-hijack defence (F52)."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import httpx
from sqlalchemy import func, select

from docify.db.models import GithubInstallation, Job, Repository, WorkspaceInstallation
from docify.db.session import session_scope
from docify.email.sender import MemorySender
from tests.helpers.github import FakeGitHub
from tests.integration.conftest import make_user, make_workspace


async def _install(c: httpx.AsyncClient, slug: str, installation_id: int) -> httpx.Response:
    r = await c.get(f"/api/workspaces/{slug}/github/install-url")
    assert r.status_code == 200
    url = r.json()["url"]
    assert url.startswith("https://github.com/apps/docify-test/installations/new?state=")
    state = parse_qs(urlparse(url).query)["state"][0]
    r = await c.get(f"/api/github/setup?installation_id={installation_id}&setup_action=install&state={state}")
    assert r.status_code == 302
    oauth_state = parse_qs(urlparse(r.headers["location"]).query)["state"][0]
    return await c.get(f"/api/auth/github/callback?code=c0de&state={oauth_state}")


async def test_install_attach_and_index_job(outbox: MemorySender, gh: FakeGitHub) -> None:
    c = await make_user(outbox, "own@example.com")
    ws = await make_workspace(c, "Acme")
    r = await _install(c, ws["slug"], gh.installation_id)
    assert r.headers["location"].endswith(f"/w/{ws['slug']}/repos?connected=1")
    insts = (await c.get(f"/api/workspaces/{ws['slug']}/github/installations")).json()
    assert insts[0]["account_login"] == "acme"
    assert insts[0]["repos"][0]["full_name"] == "acme/taskly"
    assert insts[0]["repos"][0]["attached_workspace"] is None
    r = await c.post(f"/api/workspaces/{ws['slug']}/github/installations/{gh.installation_id}/repos",
                     json={"github_repo_ids": [gh.repo_id]})
    assert r.status_code == 201, r.text
    assert r.json()[0]["status"] == "pending"
    async with session_scope() as db:
        assert (await db.execute(select(Job.type))).scalars().all() == ["repo_index"]
    # Same repo can't be attached twice.
    r = await c.post(f"/api/workspaces/{ws['slug']}/github/installations/{gh.installation_id}/repos",
                     json={"github_repo_ids": [gh.repo_id]})
    assert r.status_code == 409


async def test_installation_hijack_rejected(outbox: MemorySender, gh: FakeGitHub) -> None:
    c = await make_user(outbox, "mallory@example.com")
    ws = await make_workspace(c, "Evil")
    gh.user_installations = [12345]  # the OAuth user does NOT have access to installation 99
    r = await _install(c, ws["slug"], gh.installation_id)
    assert "error=install_not_yours" in r.headers["location"]
    async with session_scope() as db:
        assert (await db.execute(select(func.count()).select_from(WorkspaceInstallation))).scalar_one() == 0
        assert (await db.execute(select(func.count()).select_from(GithubInstallation))).scalar_one() == 0


async def test_member_cannot_install(outbox: MemorySender, gh: FakeGitHub) -> None:
    admin = await make_user(outbox, "ad2@example.com")
    ws = await make_workspace(admin)
    async with session_scope() as db:
        from docify.db.models import Membership, User

        member = await make_user(outbox, "m2@example.com")
        uid = (await db.execute(select(User.id).where(User.email == "m2@example.com"))).scalar_one()
        db.add(Membership(workspace_id=ws["id"], user_id=uid, role="member"))
    assert (await member.get(f"/api/workspaces/{ws['slug']}/github/install-url")).status_code == 403


async def test_repo_limit(outbox: MemorySender, gh: FakeGitHub) -> None:
    from docify.config import get_settings

    c = await make_user(outbox, "lim@example.com")
    ws = await make_workspace(c)
    await _install(c, ws["slug"], gh.installation_id)
    async with session_scope() as db:
        for i in range(get_settings().ws_max_repos):
            db.add(Repository(workspace_id=ws["id"], installation_id=gh.installation_id, github_repo_id=9000 + i,
                              owner="o", name=f"r{i}", full_name=f"o/r{i}", default_branch="main"))
    r = await c.post(f"/api/workspaces/{ws['slug']}/github/installations/{gh.installation_id}/repos",
                     json={"github_repo_ids": [gh.repo_id]})
    assert r.status_code == 409
    assert r.json()["code"] == "repo_limit"
