"""GitHub App API client (Master Doc §9.3).

- App JWT (RS256, iat = now-60s, exp <= 10 min) → installation token (1 h), cached in Valkey 50 min.
- Rate-limit aware: low remaining / secondary limits raise RetryableError with a delay,
  so the job is requeued instead of holding a worker slot.
"""

from __future__ import annotations

import contextlib
import time
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
import jwt

from docify.cache import get_valkey
from docify.config import get_settings
from docify.jobs.errors import NonRetryableError, RetryableError
from docify.observability.metrics import GITHUB_RATELIMIT, GITHUB_REQUESTS

API_VERSION = "2022-11-28"
TOKEN_CACHE_S = 50 * 60


class GitHubNotFound(Exception):
    pass


def app_jwt() -> str:
    s = get_settings()
    key = s.github_app_private_key.get_secret_value().replace("\\n", "\n")
    if not (s.github_app_id and key):
        raise NonRetryableError("GitHub App is not configured.", code="github_not_configured")
    now = int(time.time())
    return jwt.encode({"iat": now - 60, "exp": now + 9 * 60, "iss": s.github_app_id}, key, algorithm="RS256")


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": API_VERSION, "User-Agent": "docify"}


def _check(r: httpx.Response, installation_id: int | None = None) -> None:
    GITHUB_REQUESTS.labels(str(r.status_code)).inc()
    remaining = r.headers.get("x-ratelimit-remaining")
    if remaining is not None and installation_id is not None:
        GITHUB_RATELIMIT.labels(str(installation_id)).set(int(remaining))
    if r.status_code in (403, 429) and (r.headers.get("retry-after") or remaining == "0"):
        retry_after = r.headers.get("retry-after")
        if retry_after:
            delay = int(retry_after)
        else:
            delay = max(1, int(r.headers.get("x-ratelimit-reset", time.time() + 60)) - int(time.time()))
        raise RetryableError("GitHub rate limit", delay_s=min(delay + 5, 900))
    if r.status_code >= 500:
        raise RetryableError(f"GitHub {r.status_code}")
    if remaining is not None and int(remaining) < 100 and r.status_code < 300:
        # Leave headroom for other repos; slow this job down (§9.3).
        reset = int(r.headers.get("x-ratelimit-reset", time.time() + 300))
        if reset - time.time() > 0 and int(remaining) < 20:
            raise RetryableError("GitHub rate limit nearly exhausted", delay_s=min(int(reset - time.time()) + 5, 900))


class GitHubApp:
    """App-level calls (JWT auth) + factory for installation clients."""

    def __init__(self, http: httpx.AsyncClient | None = None) -> None:
        self.s = get_settings()
        self.http = http or httpx.AsyncClient(timeout=30, follow_redirects=True)

    async def aclose(self) -> None:
        await self.http.aclose()

    async def get_installation(self, installation_id: int) -> dict[str, Any]:
        r = await self.http.get(f"{self.s.github_api_url}/app/installations/{installation_id}",
                                headers=_headers(app_jwt()))
        if r.status_code == 404:
            raise GitHubNotFound(f"installation {installation_id}")
        _check(r)
        r.raise_for_status()
        return dict(r.json())

    async def installation_token(self, installation_id: int, *, force: bool = False) -> str:
        cache_key = f"ghinst:{installation_id}"
        valkey = get_valkey()
        if not force:
            try:
                cached = await valkey.get(cache_key)
                if cached:
                    return str(cached)
            except Exception:  # noqa: S110 - cache is optional
                pass
        r = await self.http.post(f"{self.s.github_api_url}/app/installations/{installation_id}/access_tokens",
                                 headers=_headers(app_jwt()))
        if r.status_code == 404:
            raise NonRetryableError("Docify can no longer access this GitHub installation.",
                                    code="installation_gone", repo_status="disconnected")
        if r.status_code == 403:  # e.g. installation suspended: pause, don't purge (F11)
            raise NonRetryableError("The GitHub installation is suspended.", code="installation_suspended",
                                    repo_status="suspended")
        _check(r)
        r.raise_for_status()
        token = str(r.json()["token"])
        with contextlib.suppress(Exception):
            await valkey.set(cache_key, token, ex=TOKEN_CACHE_S)
        return token

    async def for_installation(self, installation_id: int) -> InstallationClient:
        return InstallationClient(self, installation_id, await self.installation_token(installation_id))


class InstallationClient:
    def __init__(self, app: GitHubApp, installation_id: int, token: str) -> None:
        self.app, self.installation_id, self.token = app, installation_id, token
        self.base = app.s.github_api_url

    async def _get(self, path: str, *, params: dict[str, Any] | None = None, allow_404: bool = False) -> httpx.Response:
        url = path if path.startswith("http") else f"{self.base}{path}"
        r = await self.app.http.get(url, headers=_headers(self.token), params=params)
        if r.status_code == 401:  # token expired/revoked early → refresh once
            self.token = await self.app.installation_token(self.installation_id, force=True)
            r = await self.app.http.get(url, headers=_headers(self.token), params=params)
        _check(r, self.installation_id)
        if r.status_code == 404 and not allow_404:
            raise GitHubNotFound(path)
        return r

    async def list_repos(self) -> list[dict[str, Any]]:
        repos: list[dict[str, Any]] = []
        url: str | None = "/installation/repositories"
        params: dict[str, Any] | None = {"per_page": 100}
        while url:
            r = await self._get(url, params=params)
            repos.extend(r.json().get("repositories", []))
            url, params = r.links.get("next", {}).get("url"), None
            if len(repos) > 2000:
                break
        return repos

    async def get_repo(self, full_name: str, github_repo_id: int) -> dict[str, Any]:
        """Use owner/name; on 404/301 fall back to the stable numeric id (handles renames/transfers)."""
        r = await self._get(f"/repos/{full_name}", allow_404=True)
        if r.status_code == 404:
            r = await self._get(f"/repositories/{github_repo_id}", allow_404=True)
            if r.status_code == 404:
                raise GitHubNotFound(full_name)
        r.raise_for_status()
        return dict(r.json())

    async def branch_head(self, full_name: str, branch: str) -> str | None:
        r = await self._get(f"/repos/{full_name}/commits/{branch}", allow_404=True)
        if r.status_code in (404, 409, 422):  # empty repo / missing branch
            return None
        r.raise_for_status()
        return str(r.json()["sha"])

    async def compare(self, full_name: str, base: str, head: str) -> dict[str, Any] | None:
        r = await self._get(f"/repos/{full_name}/compare/{base}...{head}", allow_404=True)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return dict(r.json())

    async def get_file(self, full_name: str, path: str, ref: str) -> bytes | None:
        r = await self.app.http.get(
            f"{self.base}/repos/{full_name}/contents/{quote(path)}", params={"ref": ref},
            headers={**_headers(self.token), "Accept": "application/vnd.github.raw+json"},
        )
        _check(r, self.installation_id)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.content

    async def list_commits(self, full_name: str, sha: str, *, max_commits: int = 200) -> list[dict[str, Any]]:
        """Newest-first history reachable from `sha` (no per-commit file lists - see `get_commit`)."""
        out: list[dict[str, Any]] = []
        page = 1
        while len(out) < max_commits:
            r = await self._get(f"/repos/{full_name}/commits", params={"sha": sha, "per_page": 100, "page": page},
                                allow_404=True)
            if r.status_code != 200:
                break
            batch = r.json()
            if not isinstance(batch, list) or not batch:
                break
            out.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return out[:max_commits]

    async def get_commit(self, full_name: str, sha: str) -> dict[str, Any] | None:
        r = await self._get(f"/repos/{full_name}/commits/{sha}", allow_404=True)
        if r.status_code != 200:
            return None
        return dict(r.json())

    async def blame(self, full_name: str, ref: str, path: str) -> list[dict[str, Any]]:
        """Line ranges -> commit/author for one file (GraphQL; installation tokens need only contents:read)."""
        owner, name = full_name.split("/", 1)
        query = ("query($o:String!,$n:String!,$e:String!,$p:String!){repository(owner:$o,name:$n){object(expression:$e)"
                 "{... on Commit{blame(path:$p){ranges{startingLine endingLine commit{oid committedDate messageHeadline"
                 " author{name user{login}}}}}}}}}")
        r = await self.app.http.post(f"{self.base}/graphql", headers=_headers(self.token),
                                     json={"query": query, "variables": {"o": owner, "n": name, "e": ref, "p": path}})
        _check(r, self.installation_id)
        r.raise_for_status()
        obj = (((r.json().get("data") or {}).get("repository") or {}).get("object") or {})
        out = []
        for rg in ((obj.get("blame") or {}).get("ranges") or []):
            c = rg.get("commit") or {}
            a = c.get("author") or {}
            when = c.get("committedDate")
            out.append({"start": rg["startingLine"], "end": rg["endingLine"], "sha": c.get("oid"),
                        "message": c.get("messageHeadline"), "name": a.get("name") or "unknown",
                        "login": (a.get("user") or {}).get("login"),
                        "date": datetime.fromisoformat(when.replace("Z", "+00:00")) if when else None})
        return out

    async def list_issues(self, full_name: str, *, state: str = "all", limit: int = 100) -> list[dict[str, Any]]:
        """Issues (not PRs). Needs issues:read for private repos; public repos fall back to anonymous reads."""
        params: dict[str, Any] = {"state": state, "per_page": min(limit, 100), "sort": "updated"}
        r = await self._get(f"/repos/{full_name}/issues", params=params, allow_404=True)
        if r.status_code in (403, 404):
            r = await self.app.http.get(f"{self.base}/repos/{full_name}/issues", params=params,
                                        headers={"Accept": "application/vnd.github+json",
                                                 "X-GitHub-Api-Version": "2022-11-28"})
        if r.status_code != 200:
            raise GitHubNotFound(f"issues of {full_name} ({r.status_code})")
        return [i for i in r.json() if "pull_request" not in i][:limit]

    async def languages(self, full_name: str) -> dict[str, int]:
        r = await self._get(f"/repos/{full_name}/languages", allow_404=True)
        return dict(r.json()) if r.status_code == 200 else {}

    async def list_pulls(self, full_name: str, *, limit: int = 100) -> list[dict[str, Any]]:
        r = await self._get(f"/repos/{full_name}/pulls", params={"state": "all", "per_page": min(limit, 100),
                                                                "sort": "updated", "direction": "desc"},
                            allow_404=True)
        return list(r.json()) if r.status_code == 200 else []

    async def pulls_for_commit(self, full_name: str, sha: str) -> list[dict[str, Any]]:
        r = await self._get(f"/repos/{full_name}/commits/{sha}/pulls", allow_404=True)
        if r.status_code != 200:
            return []
        return list(r.json())

    async def download_tarball(self, full_name: str, sha: str, dest: Path, *, max_bytes: int) -> None:
        """Stream the tarball to disk, enforcing the byte cap *while* streaming (§9.3)."""
        url = f"{self.base}/repos/{full_name}/tarball/{sha}"
        async with self.app.http.stream("GET", url, headers=_headers(self.token)) as r:
            if r.status_code in (404, 409):
                raise NonRetryableError("Repository is empty.", code="empty", repo_status="empty")
            _check(r, self.installation_id)
            r.raise_for_status()
            size = 0
            with open(dest, "wb") as fh:
                async for chunk in _iter(r):
                    size += len(chunk)
                    if size > max_bytes:
                        raise NonRetryableError(
                            f"Repository is larger than {max_bytes // (1024 * 1024)} MB.",
                            code="too_large", repo_status="too_large")
                    fh.write(chunk)


async def _iter(r: httpx.Response) -> AsyncIterator[bytes]:
    async for chunk in r.aiter_bytes(64 * 1024):
        yield chunk
