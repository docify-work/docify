"""Fake GitHub for tests: a throwaway RSA key (generated at import, never stored) + respx routes."""

from __future__ import annotations

import io
import tarfile
from pathlib import Path
from typing import Any

import httpx
import respx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
RSA_PRIVATE_PEM = _key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                     serialization.NoEncryption()).decode()

API = "https://api.github.com"
WEB = "https://github.com"
FIXTURE = Path(__file__).resolve().parents[2] / "src" / "docify" / "demo" / "eval_data" / "fixture-repo"


def make_tarball(files: dict[str, bytes], prefix: str = "acme-taskly-abc123") -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for path, data in files.items():
            info = tarfile.TarInfo(f"{prefix}/{path}")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def fixture_files() -> dict[str, bytes]:
    return {p.relative_to(FIXTURE).as_posix(): p.read_bytes() for p in FIXTURE.rglob("*") if p.is_file()}


def fake_commit(sha: str, name: str, login: str, date: str, message: str, files: list[str],
                patches: dict[str, str] | None = None) -> dict[str, Any]:
    patches = patches or {}
    return {"sha": sha, "author": {"login": login},
            "commit": {"message": message, "author": {"name": name, "email": f"{login}@example.com", "date": date}},
            "files": [{"filename": f, "status": "modified", **({"patch": patches[f]} if f in patches else {})}
                      for f in files],
            "stats": {"additions": 10, "deletions": 1}}


class FakeGitHub:
    """Stateful fake for one installation with one repo. Tests mutate `files`, `head`, `compare`."""

    def __init__(self, mock: respx.MockRouter, *, installation_id: int = 99, repo_id: int = 555,
                 full_name: str = "acme/taskly", account: str = "acme") -> None:
        self.mock = mock
        self.installation_id, self.repo_id, self.full_name, self.account = installation_id, repo_id, full_name, account
        self.default_branch = "main"
        self.head = "a" * 40
        self.files = fixture_files()
        self.compare: dict[str, Any] | None = None
        self.history: list[dict[str, Any]] = [
            fake_commit("a" * 40, "Ada Lovelace", "ada", "2026-10-01T10:00:00Z", "Initial commit",
                        ["README.md", "app/main.py"]),
            fake_commit("c" * 40, "Grace Hopper", "grace", "2026-10-05T12:30:00Z",
                        "Add password hashing with bcrypt (#3)", ["app/auth.py"]),
        ]
        self.user_installations = [installation_id]
        self.github_user = {"id": 777, "login": "octo", "name": "Octo Cat", "avatar_url": None}
        self.emails = [{"email": "octo@example.com", "primary": True, "verified": True}]
        self.issues: list[dict[str, Any]] = [
            {"number": 1, "title": "Password hashing is too slow on login", "state": "open", "user": {"login": "zoe"},
             "labels": [{"name": "bug"}], "comments": 2, "html_url": "https://github.com/acme/taskly/issues/1",
             "created_at": "2026-10-20T10:00:00Z", "body": "Login takes 3 s; see app/auth.py"},
            {"number": 2, "title": "A pull request", "state": "open", "user": {"login": "zoe"}, "labels": [],
             "comments": 0, "html_url": "https://github.com/acme/taskly/pull/2", "pull_request": {},
             "created_at": "2026-10-21T10:00:00Z"},
        ]
        self.blame_login = "grace"
        self.suspended = False
        self.user_sees_repo = True  # org member with read access to this repo?
        self.calls: list[str] = []
        self._routes()

    def repo_json(self) -> dict[str, Any]:
        owner, name = self.full_name.split("/")
        return {"id": self.repo_id, "name": name, "full_name": self.full_name, "owner": {"login": owner},
                "default_branch": self.default_branch, "private": False, "archived": False, "size": 100}

    def _routes(self) -> None:
        m, inst = self.mock, self.installation_id
        m.post(f"{API}/app/installations/{inst}/access_tokens").mock(
            return_value=httpx.Response(201, json={"token": "ghs_test_installation_token"}))
        m.get(f"{API}/app/installations/{inst}").mock(side_effect=lambda req: httpx.Response(200, json={
            "id": inst, "account": {"login": self.account, "type": "User"}, "repository_selection": "selected",
            "permissions": {"contents": "read"}, "suspended_at": "2026-01-01T00:00:00Z" if self.suspended else None}))
        m.get(f"{API}/installation/repositories").mock(
            side_effect=lambda req: httpx.Response(200, json={"repositories": [self.repo_json()]}))
        m.get(f"{API}/repos/{self.full_name}").mock(side_effect=lambda req: httpx.Response(200, json=self.repo_json()))
        m.get(f"{API}/repositories/{self.repo_id}").mock(
            side_effect=lambda req: httpx.Response(200, json=self.repo_json()))
        m.get(url__regex=rf"{API}/repos/{self.full_name}/commits(\?.*)?$").mock(side_effect=self._list_commits)
        m.get(url__regex=rf"{API}/repos/{self.full_name}/commits/[^/?]+$").mock(side_effect=self._commit)
        m.get(url__regex=rf"{API}/repos/{self.full_name}/commits/[^/]+/pulls").mock(
            return_value=httpx.Response(200, json=[]))
        m.get(url__regex=rf"{API}/repos/{self.full_name}/tarball/.+").mock(side_effect=self._tarball)
        m.get(url__regex=rf"{API}/repos/{self.full_name}/languages").mock(
            return_value=httpx.Response(200, json={"Python": 12000, "Markdown": 800}))
        m.get(url__regex=rf"{API}/repos/{self.full_name}/pulls.*").mock(return_value=httpx.Response(200, json=[
            {"number": 3, "title": "Add bcrypt", "state": "closed", "merged_at": "2026-10-05T14:30:00Z",
             "created_at": "2026-10-05T12:30:00Z", "updated_at": "2026-10-05T14:30:00Z", "user": {"login": "grace"},
             "html_url": "https://github.com/acme/taskly/pull/3"}]))
        m.get(url__regex=rf"{API}/repos/{self.full_name}/issues.*").mock(
            side_effect=lambda req: httpx.Response(200, json=self.issues))
        m.post(f"{API}/graphql").mock(side_effect=self._graphql)
        m.get(url__regex=rf"{API}/repos/{self.full_name}/compare/.+").mock(side_effect=self._compare)
        m.get(url__regex=rf"{API}/repos/{self.full_name}/contents/.+").mock(side_effect=self._contents)
        # OAuth (user-to-server)
        m.post(f"{WEB}/login/oauth/access_token").mock(
            return_value=httpx.Response(200, json={"access_token": "ghu_user_token", "token_type": "bearer"}))
        m.get(f"{API}/user").mock(side_effect=lambda req: httpx.Response(200, json=self.github_user))
        m.get(f"{API}/user/emails").mock(side_effect=lambda req: httpx.Response(200, json=self.emails))
        m.get(url__regex=rf"{API}/user/installations/\d+/repositories.*").mock(
            side_effect=lambda req: httpx.Response(200, json={"repositories": [
                self.repo_json()] if self.user_sees_repo else []}))
        m.get(url__startswith=f"{API}/user/installations").mock(side_effect=lambda req: httpx.Response(
            200, json={"installations": [{"id": i} for i in self.user_installations]}))

    def _list_commits(self, request: httpx.Request) -> httpx.Response:
        self.calls.append("list_commits")
        page = int(request.url.params.get("page", "1"))
        items = sorted(self.history, key=lambda c: c["commit"]["author"]["date"], reverse=True)
        return httpx.Response(200, json=[{k: v for k, v in c.items() if k != "files"} for c in items]
                              if page == 1 else [])

    def _commit(self, request: httpx.Request) -> httpx.Response:
        ref = request.url.path.rsplit("/", 1)[1]
        found = next((c for c in self.history if c["sha"] == ref), None)
        return httpx.Response(200, json=found if found else {"sha": self.head})

    def _graphql(self, request: httpx.Request) -> httpx.Response:
        import json as _json

        path = _json.loads(request.content)["variables"]["p"]
        n = max(1, (self.files.get(path) or b"").count(b"\n") + 1)
        return httpx.Response(200, json={"data": {"repository": {"object": {"blame": {"ranges": [
            {"startingLine": 1, "endingLine": n, "commit": {"oid": "c" * 40, "committedDate": "2026-10-05T12:30:00Z",
                                                            "messageHeadline": "Add password hashing with bcrypt (#3)",
                                                            "author": {"name": "Grace Hopper",
                                                                       "user": {"login": self.blame_login}}}}]}}}}})

    def _tarball(self, request: httpx.Request) -> httpx.Response:
        self.calls.append("tarball")
        return httpx.Response(200, content=make_tarball(self.files))

    def _compare(self, request: httpx.Request) -> httpx.Response:
        self.calls.append("compare")
        if self.compare is None:
            return httpx.Response(404)
        return httpx.Response(200, json=self.compare)

    def _contents(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path.split("/contents/", 1)[1]
        self.calls.append(f"contents:{path}")
        data = self.files.get(path)
        return httpx.Response(200, content=data) if data is not None else httpx.Response(404)
