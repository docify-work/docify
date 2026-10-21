"""OAuth 2.0 / OIDC clients for GitHub (App user-to-server) and Google (Master Doc §10.2).

We use plain httpx + PyJWT instead of a framework so every step is visible and
testable with `respx`. Provider access tokens are used once and discarded.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt

from docify.config import get_settings

GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
GOOGLE_JWKS = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = ("https://accounts.google.com", "accounts.google.com")


class OAuthError(Exception):
    """Something went wrong talking to the provider; message is safe to show."""


@dataclass
class ProviderProfile:
    provider: str
    provider_user_id: str
    email: str | None
    email_verified: bool
    name: str | None
    avatar_url: str | None
    login: str | None = None
    access_token: str | None = None  # only used immediately (e.g. /user/installations), never stored


def pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def callback_url(provider: str) -> str:
    return f"{get_settings().public_base_url.rstrip('/')}/api/auth/{provider}/callback"


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=10, headers={"User-Agent": "docify"})


# ----------------------------------------------------------------------------- GitHub


def github_authorize_url(state: str, code_challenge: str) -> str:
    s = get_settings()
    q = {"client_id": s.github_client_id, "redirect_uri": callback_url("github"), "state": state,
         "code_challenge": code_challenge, "code_challenge_method": "S256", "allow_signup": "true"}
    return f"{s.github_web_url}/login/oauth/authorize?{urlencode(q)}"


async def github_exchange(code: str, code_verifier: str | None) -> ProviderProfile:
    s = get_settings()
    async with _client() as client:
        data = {"client_id": s.github_client_id, "client_secret": s.github_client_secret.get_secret_value(),
                "code": code, "redirect_uri": callback_url("github")}
        if code_verifier:
            data["code_verifier"] = code_verifier
        r = await client.post(f"{s.github_web_url}/login/oauth/access_token", data=data,
                              headers={"Accept": "application/json"})
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        token = body.get("access_token")
        if r.status_code != 200 or not token:
            raise OAuthError("GitHub sign-in failed. Please try again.")
        auth = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28"}
        u = await client.get(f"{s.github_api_url}/user", headers=auth)
        if u.status_code != 200:
            raise OAuthError("Could not read your GitHub profile.")
        user = u.json()
        e = await client.get(f"{s.github_api_url}/user/emails", headers=auth)
        emails: list[dict[str, Any]] = e.json() if e.status_code == 200 else []
    primary = next((m for m in emails if m.get("primary")), None)
    return ProviderProfile(
        provider="github", provider_user_id=str(user["id"]),
        email=primary["email"] if primary else None,
        email_verified=bool(primary and primary.get("verified")),
        name=user.get("name") or user.get("login"), avatar_url=user.get("avatar_url"),
        login=user.get("login"), access_token=token,
    )


async def github_user_installation_ids(access_token: str) -> set[int]:
    """Installations the *user* can access — used to verify install ownership (§9.2 step 3)."""
    s = get_settings()
    ids: set[int] = set()
    url: str | None = f"{s.github_api_url}/user/installations?per_page=100"
    async with _client() as client:
        for _ in range(10):  # max 1000 installations, plenty
            if url is None:
                break
            r = await client.get(url, headers={"Authorization": f"Bearer {access_token}",
                                               "Accept": "application/vnd.github+json"})
            if r.status_code != 200:
                raise OAuthError("Could not verify your GitHub installation.")
            ids.update(int(i["id"]) for i in r.json().get("installations", []))
            url = r.links.get("next", {}).get("url")
    return ids


# ----------------------------------------------------------------------------- Google


def google_authorize_url(state: str, code_challenge: str, nonce: str) -> str:
    s = get_settings()
    q = {"client_id": s.google_client_id, "redirect_uri": callback_url("google"), "response_type": "code",
         "scope": "openid email profile", "state": state, "nonce": nonce,
         "code_challenge": code_challenge, "code_challenge_method": "S256", "prompt": "select_account"}
    return f"{GOOGLE_AUTH}?{urlencode(q)}"


_jwks_cache: tuple[float, dict[str, Any]] | None = None


async def _google_jwks(client: httpx.AsyncClient) -> dict[str, Any]:
    global _jwks_cache
    if _jwks_cache and _jwks_cache[0] > time.time():
        return _jwks_cache[1]
    r = await client.get(GOOGLE_JWKS)
    r.raise_for_status()
    _jwks_cache = (time.time() + 3600, r.json())
    return _jwks_cache[1]


async def google_exchange(code: str, code_verifier: str | None, nonce: str | None) -> ProviderProfile:
    s = get_settings()
    async with _client() as client:
        data = {"client_id": s.google_client_id, "client_secret": s.google_client_secret.get_secret_value(),
                "code": code, "grant_type": "authorization_code", "redirect_uri": callback_url("google")}
        if code_verifier:
            data["code_verifier"] = code_verifier
        r = await client.post(GOOGLE_TOKEN, data=data)
        if r.status_code != 200 or "id_token" not in r.json():
            raise OAuthError("Google sign-in failed. Please try again.")
        id_token = r.json()["id_token"]
        jwks = await _google_jwks(client)
    try:
        header = jwt.get_unverified_header(id_token)
        key_data = next(k for k in jwks.get("keys", []) if k.get("kid") == header.get("kid"))
        key = jwt.PyJWK(key_data).key
        claims = jwt.decode(id_token, key=key, algorithms=["RS256"], audience=s.google_client_id,
                            options={"require": ["iss", "aud", "exp", "sub"]}, leeway=60)
    except (StopIteration, jwt.PyJWTError) as exc:
        raise OAuthError("Google sign-in could not be verified.") from exc
    if claims.get("iss") not in GOOGLE_ISSUERS or (nonce and claims.get("nonce") != nonce):
        raise OAuthError("Google sign-in could not be verified.")
    return ProviderProfile(
        provider="google", provider_user_id=str(claims["sub"]), email=claims.get("email"),
        email_verified=bool(claims.get("email_verified")), name=claims.get("name"),
        avatar_url=claims.get("picture"),
    )
