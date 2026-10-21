"""Workspaces, roles, invites and cross-tenant isolation (§10.6 mandatory tests)."""

from __future__ import annotations

import re

import httpx

from docify.db.models import (
    ChatThread,
    Chunk,
    Document,
    DocumentVersion,
    File,
    Job,
    Repository,
)
from docify.db.session import session_scope
from docify.email.sender import MemorySender
from tests.integration.conftest import make_user, make_workspace

INVITE_RE = re.compile(r"/invite/([A-Za-z0-9_\-]+)")


async def test_create_and_settings(outbox: MemorySender) -> None:
    c = await make_user(outbox, "ad@example.com")
    ws = await make_workspace(c, "Acme Team")
    assert ws["slug"] == "acme-team"
    assert ws["role"] == "admin"
    assert ws["settings"] == {"auto_publish": True, "chat_enabled": True}
    r = await c.patch(f"/api/workspaces/{ws['slug']}", json={"settings": {"auto_publish": False}})
    assert r.json()["settings"]["auto_publish"] is False
    # Slug collision gets a suffix.
    ws2 = await make_workspace(c, "Acme Team")
    assert ws2["slug"] != ws["slug"]


async def test_invite_flow_and_roles(outbox: MemorySender) -> None:
    admin = await make_user(outbox, "boss@example.com")
    ws = await make_workspace(admin)
    r = await admin.post(f"/api/workspaces/{ws['slug']}/invites", json={"email": "mem@example.com", "role": "member"})
    assert r.status_code == 201
    token = INVITE_RE.search(outbox.outbox[-1].text).group(1)  # type: ignore[union-attr]
    # Wrong user can't accept.
    stranger = await make_user(outbox, "stranger@example.com")
    r = await stranger.post(f"/api/invites/{token}/accept")
    assert r.status_code == 403
    member = await make_user(outbox, "mem@example.com")
    assert (await member.get(f"/api/invites/{token}")).json()["workspace_name"] == "Acme Team"
    r = await member.post(f"/api/invites/{token}/accept")
    assert r.status_code == 200
    assert r.json()["role"] == "member"
    # Used invite is gone.
    assert (await member.post(f"/api/invites/{token}/accept")).status_code == 404
    # Members can read but not administer.
    assert (await member.get(f"/api/workspaces/{ws['slug']}/members")).status_code == 200
    r = await member.patch(f"/api/workspaces/{ws['slug']}", json={"name": "Hacked"})
    assert r.status_code == 403
    # Last admin can't leave or be demoted.
    me_id = (await admin.get("/api/me")).json()["id"]
    r = await admin.patch(f"/api/workspaces/{ws['slug']}/members/{me_id}", json={"role": "member"})
    assert r.json()["code"] == "last_admin"
    assert (await admin.post(f"/api/workspaces/{ws['slug']}/leave")).status_code == 409
    assert (await member.post(f"/api/workspaces/{ws['slug']}/leave")).status_code == 200


async def test_cross_tenant_reads_are_404(outbox: MemorySender) -> None:
    a = await make_user(outbox, "alice@example.com")
    b = await make_user(outbox, "bob@example.com")
    ws_a = await make_workspace(a, "Alpha")
    await make_workspace(b, "Beta")
    async with session_scope() as db:
        repo = Repository(workspace_id=ws_a["id"], installation_id=1, github_repo_id=1001, owner="o", name="r",
                          full_name="o/r", default_branch="main", status="ready", last_processed_sha="a" * 40)
        db.add(repo)
        await db.flush()
        f = File(workspace_id=ws_a["id"], repo_id=repo.id, path="a.py", blob_sha="x", size=1, line_count=1)
        db.add(f)
        await db.flush()
        db.add(Chunk(workspace_id=ws_a["id"], repo_id=repo.id, file_id=f.id, path="a.py", start_line=1, end_line=1,
                     commit_sha="a" * 40, content="secret_function()", content_hash="h", search_text="secret function"))
        doc = Document(workspace_id=ws_a["id"], repo_id=repo.id, kind="overview", title="T")
        db.add(doc)
        await db.flush()
        v = DocumentVersion(workspace_id=ws_a["id"], document_id=doc.id, version=1, content_md="# T", commit_sha="a" * 40,
                            status="published")
        db.add(v)
        job = Job(workspace_id=ws_a["id"], repo_id=repo.id, type="repo_sync", status="failed")
        thread = ChatThread(workspace_id=ws_a["id"], user_id=None)
        db.add_all([job, thread])
        await db.flush()
        ids = {"repo": repo.id, "doc": doc.id, "job": job.id, "thread": thread.id, "version": v.id}
    for url in (f"/api/repos/{ids['repo']}", f"/api/docs/{ids['doc']}", f"/api/docs/{ids['doc']}/versions",
                f"/api/repos/{ids['repo']}/changelog", f"/api/chat/threads/{ids['thread']}",
                f"/api/workspaces/{ws_a['slug']}", f"/api/workspaces/{ws_a['slug']}/repos",
                f"/api/workspaces/{ws_a['slug']}/search?q=secret"):
        assert (await b.get(url)).status_code == 404, url
    for method, url in (("POST", f"/api/jobs/{ids['job']}/retry"), ("POST", f"/api/repos/{ids['repo']}/resync"),
                        ("DELETE", f"/api/repos/{ids['repo']}"), ("POST", f"/api/review/doc/{ids['version']}/approve")):
        assert (await b.request(method, url)).status_code == 404, url
    # And the owner can see them.
    assert (await a.get(f"/api/repos/{ids['repo']}")).status_code == 200
    assert (await a.get(f"/api/docs/{ids['doc']}")).status_code == 200


async def test_anonymous_writes_401_and_demo_read(anon: httpx.AsyncClient, outbox: MemorySender) -> None:
    assert (await anon.post("/api/workspaces", json={"name": "Nope"})).status_code == 401
    assert (await anon.get("/api/workspaces")).status_code == 401
    admin = await make_user(outbox, "owner@example.com")
    ws = await make_workspace(admin, "Private")
    assert (await anon.get(f"/api/workspaces/{ws['slug']}")).status_code == 404
    async with session_scope() as db:
        from docify.db.models import Workspace

        db.add(Workspace(slug="demo", name="Docify Demo", is_public_demo=True))
    assert (await anon.get("/api/demo")).json() == {"workspace_slug": "demo", "available": True}
    r = await anon.get("/api/workspaces/demo")
    assert r.status_code == 200
    assert r.json()["role"] is None
    assert (await anon.patch("/api/workspaces/demo", json={"name": "x"})).status_code == 401
    assert (await anon.get("/api/workspaces/demo/members")).status_code == 401


async def test_delete_workspace_queues_purge(outbox: MemorySender) -> None:
    a = await make_user(outbox, "del@example.com")
    ws = await make_workspace(a, "Gone")
    async with session_scope() as db:
        db.add(Repository(workspace_id=ws["id"], installation_id=1, github_repo_id=2002, owner="o", name="r2",
                          full_name="o/r2", default_branch="main", status="ready"))
    assert (await a.delete(f"/api/workspaces/{ws['slug']}")).status_code == 200
    assert (await a.get(f"/api/workspaces/{ws['slug']}")).status_code == 404
    async with session_scope() as db:
        from sqlalchemy import select

        jobs = (await db.execute(select(Job.type))).scalars().all()
        assert jobs == ["repo_purge"]
