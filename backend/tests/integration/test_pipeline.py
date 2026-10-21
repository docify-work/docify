"""End to end through SQS (ElasticMQ) + worker + fake GitHub + fake AI (P4/P5 acceptance criteria)."""

from __future__ import annotations

import json
import uuid

import httpx
from sqlalchemy import func, select

from docify.db.models import (
    ChangelogEntry,
    Chunk,
    Document,
    DocumentVersion,
    File,
    GithubInstallation,
    Job,
    Repository,
    WorkspaceInstallation,
)
from docify.db.session import session_scope
from docify.email.sender import MemorySender
from docify.jobs import service
from docify.jobs.queue import get_queue
from docify.worker.runner import Runner
from tests.helpers.github import FakeGitHub
from tests.integration.conftest import make_user, make_workspace


async def drain(max_rounds: int = 50) -> int:
    """Process messages until the queue is empty. Returns how many messages were handled."""
    runner = Runner(get_queue())
    handled = empty = 0
    for _ in range(max_rounds):
        msgs = await get_queue().receive(10, wait_s=1)
        if not msgs:
            empty += 1
            if empty >= 2:
                break
            continue
        empty = 0
        for m in msgs:
            await runner.process(m)
            handled += 1
    await runner.github.aclose()
    return handled


async def setup_repo(outbox: MemorySender, gh: FakeGitHub, *, auto_publish: bool = True) -> tuple[httpx.AsyncClient,
                                                                                                    dict, uuid.UUID]:  # type: ignore[type-arg]
    c = await make_user(outbox, f"u{uuid.uuid4().hex[:6]}@example.com")
    ws = await make_workspace(c, "Pipeline")
    if not auto_publish:
        await c.patch(f"/api/workspaces/{ws['slug']}", json={"settings": {"auto_publish": False}})
    async with session_scope() as db:
        db.add(GithubInstallation(installation_id=gh.installation_id, account_login="acme", account_type="User"))
        await db.flush()
        db.add(WorkspaceInstallation(workspace_id=ws["id"], installation_id=gh.installation_id,
                                     allowed_repo_ids=[gh.repo_id]))
    r = await c.post(f"/api/workspaces/{ws['slug']}/github/installations/{gh.installation_id}/repos",
                     json={"github_repo_ids": [gh.repo_id]})
    assert r.status_code == 201, r.text
    repo_id = uuid.UUID(r.json()[0]["id"])
    await drain()
    return c, ws, repo_id


async def test_full_index_generates_docs(outbox: MemorySender, gh: FakeGitHub) -> None:
    c, ws, repo_id = await setup_repo(outbox, gh)
    repo = (await c.get(f"/api/repos/{repo_id}")).json()
    assert repo["status"] == "ready", repo
    assert repo["last_processed_sha"] == gh.head
    async with session_scope() as db:
        paths = set((await db.execute(select(File.path).where(File.repo_id == repo_id))).scalars())
        assert "app/auth.py" in paths
        assert ".env.example" in paths
        n_chunks = (await db.execute(select(func.count()).select_from(Chunk).where(Chunk.repo_id == repo_id)))\
            .scalar_one()
        missing = (await db.execute(select(func.count()).select_from(Chunk).where(
            Chunk.repo_id == repo_id, Chunk.embedding.is_(None)))).scalar_one()
        summaries = (await db.execute(select(func.count()).select_from(File).where(
            File.repo_id == repo_id, File.summary.is_not(None)))).scalar_one()
    assert n_chunks >= len(paths)
    assert missing == 0
    assert summaries > 5
    docs = (await c.get(f"/api/workspaces/{ws['slug']}/docs")).json()
    assert sorted(d["kind"] for d in docs) == ["api", "overview", "setup"]
    detail = (await c.get(f"/api/docs/{docs[0]['id']}")).json()
    assert detail["published"]["version"] == 1
    assert "https://github.com/acme/taskly/blob/" in detail["content_md"]  # citation rendered as permalink
    jobs = (await c.get(f"/api/workspaces/{ws['slug']}/jobs")).json()["items"]
    assert [j["status"] for j in jobs if j["type"] == "repo_index"] == ["succeeded"]


async def test_push_incremental_sync_updates_only_affected_docs(outbox: MemorySender, gh: FakeGitHub) -> None:
    c, _ws, repo_id = await setup_repo(outbox, gh)
    old = gh.head
    gh.head = "b" * 40
    gh.files["app/routes/tasks.py"] += b"\n\n@router.get('/stats')\ndef stats():\n    return {}\n"
    gh.compare = {"status": "ahead", "commits": [{"commit": {"message": "Add task stats endpoint (#7)"}}],
                  "files": [{"filename": "app/routes/tasks.py", "status": "modified", "sha": "x"}]}
    await get_queue().send({"v": 1, "kind": "github_event", "delivery_id": "p1", "event": "push",
                            "installation_id": gh.installation_id, "repo_id": gh.repo_id, "before": old,
                            "after": gh.head, "forced": False})
    gh.calls.clear()
    await drain()
    assert "tarball" not in gh.calls  # incremental: contents API only
    assert "contents:app/routes/tasks.py" in gh.calls
    repo = (await c.get(f"/api/repos/{repo_id}")).json()
    assert repo["last_processed_sha"] == gh.head
    async with session_scope() as db:
        versions = dict((await db.execute(select(Document.kind, func.max(DocumentVersion.version)).join(
            DocumentVersion, DocumentVersion.document_id == Document.id).where(Document.repo_id == repo_id)
            .group_by(Document.kind))).all())
        entry = (await db.execute(select(ChangelogEntry).where(ChangelogEntry.repo_id == repo_id))).scalar_one()
    assert versions["api"] == 2  # route file changed → API doc regenerated
    assert versions["overview"] == 1  # untouched
    assert entry.pr_numbers == [7]
    assert entry.status == "published"
    log = (await c.get(f"/api/repos/{repo_id}/changelog")).json()
    assert len(log["items"]) == 1


async def test_force_push_triggers_full_index(outbox: MemorySender, gh: FakeGitHub) -> None:
    _, _, repo_id = await setup_repo(outbox, gh)
    gh.head = "c" * 40
    gh.compare = {"status": "diverged", "files": [], "commits": []}
    await get_queue().send({"v": 1, "kind": "github_event", "delivery_id": "f1", "event": "push",
                            "installation_id": gh.installation_id, "repo_id": gh.repo_id, "after": gh.head,
                            "forced": True})
    gh.calls.clear()
    await drain()
    assert "tarball" in gh.calls
    async with session_scope() as db:
        repo = await db.get(Repository, repo_id)
        assert repo is not None
        assert repo.last_full_index_sha == "c" * 40


async def test_burst_of_pushes_is_coalesced(outbox: MemorySender, gh: FakeGitHub) -> None:
    _, _, repo_id = await setup_repo(outbox, gh)
    gh.head = "d" * 40
    gh.compare = {"status": "ahead", "commits": [], "files": []}
    for i in range(20):
        await get_queue().send({"v": 1, "kind": "github_event", "delivery_id": f"burst-{i}", "event": "push",
                                "installation_id": gh.installation_id, "repo_id": gh.repo_id, "after": gh.head})
    await drain()
    async with session_scope() as db:
        runs = (await db.execute(select(func.count()).select_from(Job).where(
            Job.repo_id == repo_id, Job.type == "repo_sync", Job.started_at.is_not(None)))).scalar_one()
    assert 1 <= runs <= 2  # AC: 20 rapid pushes → ≤ 2 runs


async def test_replayed_delivery_creates_no_job(outbox: MemorySender, gh: FakeGitHub) -> None:
    await setup_repo(outbox, gh)
    msg = {"v": 1, "kind": "github_event", "delivery_id": "same", "event": "push",
           "installation_id": gh.installation_id, "repo_id": gh.repo_id, "after": gh.head}
    await get_queue().send(msg)
    await drain()
    async with session_scope() as db:
        before = (await db.execute(select(func.count()).select_from(Job))).scalar_one()
    await get_queue().send(msg)
    await drain()
    async with session_scope() as db:
        assert (await db.execute(select(func.count()).select_from(Job))).scalar_one() == before


async def test_search_and_chat(outbox: MemorySender, gh: FakeGitHub) -> None:
    c, ws, _ = await setup_repo(outbox, gh)
    r = await c.get(f"/api/workspaces/{ws['slug']}/search", params={"q": "how are passwords hashed bcrypt"})
    assert r.status_code == 200
    hits = r.json()["hits"]
    assert hits
    assert any(h["path"] == "app/auth.py" for h in hits[:5])
    r = await c.get(f"/api/workspaces/{ws['slug']}/search", params={"q": "Taskly", "scope": "docs"})
    assert r.status_code == 200
    # Chat streams tokens + sources.
    async with c.stream("POST", f"/api/workspaces/{ws['slug']}/chat",
                        json={"message": "How are passwords hashed?"}) as resp:
        assert resp.status_code == 200
        body = "".join([chunk async for chunk in resp.aiter_text()])
    events = [e for e in body.split("\n\n") if e.strip()]
    kinds = [e.split("\n")[0].removeprefix("event: ") for e in events]
    assert kinds[0] == "meta"
    assert "token" in kinds
    assert "sources" in kinds
    assert kinds[-1] == "done"
    sources = json.loads(next(e for e in events if e.startswith("event: sources")).split("data: ", 1)[1])
    assert sources[0]["url"].startswith("https://github.com/acme/taskly/blob/")
    thread_id = json.loads(events[0].split("data: ", 1)[1])["thread_id"]
    thread = (await c.get(f"/api/chat/threads/{thread_id}")).json()
    assert [m["role"] for m in thread["messages"]] == ["user", "assistant"]
    # Unrelated question → no-context gate, no LLM call.
    async with c.stream("POST", f"/api/workspaces/{ws['slug']}/chat",
                        json={"message": "Kubernetes autoscaler replicas?"}) as resp:
        body = "".join([chunk async for chunk in resp.aiter_text()])
    assert "couldn't find this in the indexed code" in body


async def test_review_queue_when_approval_required(outbox: MemorySender, gh: FakeGitHub) -> None:
    c, ws, repo_id = await setup_repo(outbox, gh, auto_publish=False)
    docs = (await c.get(f"/api/workspaces/{ws['slug']}/docs")).json()
    assert all(d["published"] is None and d["has_pending_review"] for d in docs)
    queue = (await c.get(f"/api/workspaces/{ws['slug']}/review")).json()
    assert len(queue) == 3
    first = queue[0]
    assert (await c.post(f"/api/review/doc/{first['id']}/approve")).status_code == 200
    assert (await c.post(f"/api/review/doc/{first['id']}/approve")).status_code == 409
    assert (await c.post(f"/api/review/doc/{queue[1]['id']}/reject")).status_code == 200
    docs = (await c.get(f"/api/workspaces/{ws['slug']}/docs")).json()
    assert sum(1 for d in docs if d["published"]) == 1
    del repo_id


async def test_remove_repo_purges_everything(outbox: MemorySender, gh: FakeGitHub) -> None:
    c, ws, repo_id = await setup_repo(outbox, gh)
    assert (await c.delete(f"/api/repos/{repo_id}")).status_code == 202
    assert (await c.get(f"/api/repos/{repo_id}")).status_code == 404
    await drain()
    async with session_scope() as db:
        for model in (Repository, File, Chunk, Document):
            assert (await db.execute(select(func.count()).select_from(model))).scalar_one() == 0, model
    assert (await c.get(f"/api/workspaces/{ws['slug']}/repos")).json() == []


async def test_budget_block_parks_job(outbox: MemorySender, gh: FakeGitHub, monkeypatch: object) -> None:
    from docify.config import get_settings

    settings = get_settings()
    old = settings.ai_daily_budget_usd
    settings.ai_daily_budget_usd = 0.0  # everything is over budget
    try:
        c, _ws, repo_id = await setup_repo(outbox, gh)
    finally:
        settings.ai_daily_budget_usd = old
    async with session_scope() as db:
        job = (await db.execute(select(Job).where(Job.repo_id == repo_id))).scalar_one()
    assert job.status == "blocked_budget"
    # Chat is refused while over budget.
    settings.ai_daily_budget_usd = 0.0
    try:
        r = await c.post(f"/api/workspaces/{_ws['slug']}/chat", json={"message": "hi"})
        assert r.status_code == 429
        assert r.json()["code"] == "ai_budget"
    finally:
        settings.ai_daily_budget_usd = old


async def test_reconciler_requeues_stale_and_detects_new_head(outbox: MemorySender, gh: FakeGitHub) -> None:
    from docify.jobs.reconcile import reconcile_once

    _, _, repo_id = await setup_repo(outbox, gh)
    gh.head = "e" * 40  # pushed while we were asleep; webhook lost
    gh.compare = {"status": "ahead", "commits": [], "files": []}
    stats = await reconcile_once()
    assert stats["synced"] == 1
    await drain()
    async with session_scope() as db:
        repo = await db.get(Repository, repo_id)
        assert repo is not None
        assert repo.last_processed_sha == "e" * 40


async def test_retry_and_dead_jobs(outbox: MemorySender, gh: FakeGitHub) -> None:
    c, ws, repo_id = await setup_repo(outbox, gh)
    async with session_scope() as db:
        job = Job(workspace_id=uuid.UUID(ws["id"]), repo_id=repo_id, type="repo_sync", status="dead",
                  attempts=5, dedupe_key=service.dedupe_key_for("repo_sync", repo_id=repo_id))
        db.add(job)
        await db.flush()
        jid = job.id
    r = await c.post(f"/api/jobs/{jid}/retry")
    assert r.status_code == 202
    await drain()
    async with session_scope() as db:
        j = await db.get(Job, jid)
        assert j is not None
        assert j.status == "succeeded"
