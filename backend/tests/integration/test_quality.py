"""Insights, policy checks/findings and issues end to end (D66): fake GitHub + worker + API."""

from __future__ import annotations

from sqlalchemy import select

from docify.db.models import Finding
from docify.db.session import session_scope
from docify.email.sender import MemorySender
from docify.jobs.queue import get_queue
from tests.helpers.github import FakeGitHub, fake_commit
from tests.integration.test_pipeline import drain, setup_repo

H = {"X-Docify-CSRF": "1"}


async def _push(gh: FakeGitHub, sha: str, commit: dict, path: str, extra: bytes) -> None:  # type: ignore[type-arg]
    old = gh.head
    gh.head = sha
    gh.files[path] = gh.files.get(path, b"") + extra
    gh.history.append(commit)
    gh.compare = {"status": "ahead", "commits": [{k: v for k, v in commit.items() if k != "files"}],
                  "files": [{"filename": path, "status": "modified", "sha": "x"}]}
    await get_queue().send({"v": 1, "kind": "github_event", "delivery_id": f"d-{sha[:6]}", "event": "push",
                            "installation_id": gh.installation_id, "repo_id": gh.repo_id, "before": old,
                            "after": gh.head, "forced": False})
    await drain()


async def test_push_with_ai_model_name_is_flagged_and_attributed(outbox: MemorySender, gh: FakeGitHub) -> None:
    c, ws, repo_id = await setup_repo(outbox, gh)
    slug = ws["slug"]
    pols = (await c.get(f"/api/workspaces/{slug}/policies")).json()
    assert {p["template"] for p in pols} == {"secrets", "ai_models", "debug", "todo", "ip_addresses"}
    before = (await c.get(f"/api/workspaces/{slug}/findings")).json()["items"]

    patch = "@@ -1,2 +1,3 @@\n import os\n+DEFAULT_MODEL = 'gpt-4o-mini'  # shown in the footer\n x = 1"
    commit = fake_commit("e" * 40, "Mallory Dev", "mallory", "2026-10-11T09:00:00Z", "Show model in footer (#9)",
                         ["app/main.py"], patches={"app/main.py": patch})
    await _push(gh, "e" * 40, commit, "app/main.py", b"\nDEFAULT_MODEL = 'gpt-4o-mini'\n")

    items = (await c.get(f"/api/workspaces/{slug}/findings", params={"status": "open"})).json()["items"]
    new = [f for f in items if f["id"] not in {b["id"] for b in before}]
    assert len(new) == 1, new
    f = new[0]
    assert f["policy_name"] == "No AI model names in the product" and f["source"] == "push"
    assert (f["author_login"], f["path"], f["line"], f["pr_number"]) == ("mallory", "app/main.py", 2, 9)
    assert f["url"].endswith("/app/main.py#L2")

    # The same line pushed again (e.g. a revert + re-apply) is not a second finding.
    async with session_scope() as db:
        n = len((await db.execute(select(Finding).where(Finding.repo_id == repo_id))).scalars().all())
    assert n == len(before) + 1

    # Finding -> issue: the suspect is the author who added the line.
    r = await c.post(f"/api/findings/{f['id']}/issue", headers=H)
    assert r.status_code == 201, r.text
    issue = r.json()
    assert issue["source"] == "finding" and issue["suspects"][0]["login"] == "mallory"
    assert issue["suspects"][0]["confidence"] == 1.0
    again = (await c.post(f"/api/findings/{f['id']}/issue", headers=H)).json()
    assert again["id"] == issue["id"]
    # Assign it -> in progress; finding moves to acknowledged.
    r = await c.patch(f"/api/issues/{issue['id']}", json={"assignee_login": "mallory"}, headers=H)
    assert r.json()["status"] == "in_progress" and r.json()["assignee_login"] == "mallory"
    f2 = (await c.get(f"/api/workspaces/{slug}/findings")).json()["items"]
    assert next(x for x in f2 if x["id"] == f["id"])["status"] == "acknowledged"
    # Mark the finding resolved.
    r = await c.patch(f"/api/findings/{f['id']}", json={"status": "resolved"}, headers=H)
    assert r.status_code == 200 and r.json()["status"] == "resolved"


async def test_scan_now_uses_blame_and_custom_policies(outbox: MemorySender, gh: FakeGitHub) -> None:
    c, ws, repo_id = await setup_repo(outbox, gh)
    slug = ws["slug"]
    # A pattern that can hang the scanner is refused; a test endpoint helps write rules.
    bad = await c.post(f"/api/workspaces/{slug}/policies", headers=H,
                       json={"name": "Bad", "kind": "regex", "pattern": "(a+)+$"})
    assert bad.status_code == 422 and bad.json()["code"] == "invalid_pattern"
    t = (await c.post("/api/policies/test", headers=H,
                      json={"kind": "terms", "pattern": "bcrypt", "sample": "import bcrypt\nx = 1"})).json()
    assert t["ok"] and t["matches"][0]["line"] == 1
    r = await c.post(f"/api/workspaces/{slug}/policies", headers=H,
                     json={"name": "No bcrypt", "kind": "terms", "pattern": "bcrypt", "severity": "high",
                           "paths": "*.py"})
    assert r.status_code == 201, r.text
    dup = await c.post(f"/api/workspaces/{slug}/policies", headers=H, json={"name": "No bcrypt", "pattern": "x"})
    assert dup.status_code == 409
    r = await c.post(f"/api/workspaces/{slug}/checks/scan", headers=H, json={"repo_id": str(repo_id)})
    assert r.status_code == 200 and r.json()["findings_created"] >= 1
    items = (await c.get(f"/api/workspaces/{slug}/findings", params={"severity": "high"})).json()["items"]
    assert items and all(i["policy_name"] == "No bcrypt" for i in items)
    assert items[0]["author_login"] == "grace" and items[0]["source"] == "scan"  # from GraphQL blame
    # Re-scan creates nothing new; disabling + deleting policies is admin-only and keeps findings.
    again = (await c.post(f"/api/workspaces/{slug}/checks/scan", headers=H, json={})).json()
    assert again["findings_created"] == 0
    pid = r.json() and items[0]["policy_id"]
    assert (await c.patch(f"/api/policies/{pid}", headers=H, json={"enabled": False})).json()["enabled"] is False
    assert (await c.delete(f"/api/policies/{pid}", headers=H)).status_code == 200
    assert (await c.get(f"/api/workspaces/{slug}/findings", params={"severity": "high"})).json()["items"]


async def test_issue_suspects_insights_and_github_import(outbox: MemorySender, gh: FakeGitHub) -> None:
    c, ws, repo_id = await setup_repo(outbox, gh)
    slug = ws["slug"]
    r = await c.post(f"/api/workspaces/{slug}/issues", headers=H,
                     json={"title": "Login rejects valid passwords",
                           "body": "Since the bcrypt change in app/auth.py users can't log in.", "severity": "high"})
    assert r.status_code == 201, r.text
    issue = r.json()
    assert issue["number"] == 1 and issue["severity"] == "high"
    top = issue["suspects"][0]
    assert top["login"] == "grace" and top["confidence"] == 1.0
    assert any("app/auth.py" in reason["text"] for reason in top["reasons"])
    assert all(reason["url"].startswith("https://github.com/acme/taskly/commit/") for reason in top["reasons"])
    # Re-analyse, change status, list with filters.
    assert (await c.post(f"/api/issues/{issue['id']}/analyze", headers=H)).status_code == 200
    r = await c.patch(f"/api/issues/{issue['id']}", headers=H, json={"status": "resolved"})
    assert r.json()["status"] == "resolved" and r.json()["closed_at"]
    assert (await c.get(f"/api/workspaces/{slug}/issues", params={"status": "open,in_progress"})).json() == []

    # GitHub issues: PRs are filtered out; import analyses the issue text.
    gi = (await c.get(f"/api/workspaces/{slug}/github-issues", params={"repo_id": str(repo_id), "state": "all"})).json()
    assert [i["number"] for i in gi] == [1]
    r = await c.post(f"/api/workspaces/{slug}/github-issues/import", headers=H,
                     json={"repo_id": str(repo_id), "number": 1})
    assert r.status_code == 201 and r.json()["source"] == "github" and r.json()["github_author"] == "zoe"
    assert r.json()["suspects"][0]["login"] == "grace"
    gi = (await c.get(f"/api/workspaces/{slug}/github-issues", params={"repo_id": str(repo_id)})).json()
    assert gi[0]["imported_issue_number"] == r.json()["number"]

    # Insights.
    ins = (await c.get(f"/api/repos/{repo_id}/insights", params={"refresh": "true"})).json()
    assert ins["totals"]["commits"] == 2 and ins["totals"]["contributors"] == 2
    assert {p["login"] for p in ins["contributors"]} == {"ada", "grace"}
    assert ins["github"]["languages"]["Python"] == 12000
    assert ins["github"]["pulls"]["merged"] == 1 and ins["github"]["pulls"]["avg_hours_to_merge"] == 2.0
    assert len(ins["weekly_commits"]) == 26 and ins["health"]["grade"] in "ABCD"
    assert ins["totals"]["open_issues"] == 1
    people = (await c.get(f"/api/workspaces/{slug}/contributors")).json()
    assert people[0]["commits"] == 1 and {p["login"] for p in people} == {"ada", "grace"}

    # Anonymous visitors can't write.
    c.cookies.clear()
    assert (await c.post(f"/api/workspaces/{slug}/issues", headers=H, json={"title": "x y z"})).status_code == 401
