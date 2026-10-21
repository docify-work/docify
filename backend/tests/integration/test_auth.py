"""Auth flows (P1.9): email+password, verification, reset, sessions, CSRF, OAuth login, linking, takeover."""

from __future__ import annotations

import time
from urllib.parse import parse_qs, urlparse

import httpx
import jwt
import respx
from sqlalchemy import func, select

from docify.db.models import AuthIdentity, Session, User
from docify.db.session import session_scope
from docify.email.sender import MemorySender
from tests.helpers.github import RSA_PRIVATE_PEM, FakeGitHub
from tests.integration.conftest import TOKEN_RE, make_user

PW = "correct horse battery 9"


async def test_signup_verify_login_logout(client: httpx.AsyncClient, outbox: MemorySender) -> None:
    r = await client.post("/api/auth/signup", json={"email": "Ana@Example.com", "password": PW})
    assert r.status_code == 202
    # Login blocked until verified.
    r = await client.post("/api/auth/login", json={"email": "ana@example.com", "password": PW})
    assert r.status_code == 403
    assert r.json()["code"] == "email_not_verified"
    token = TOKEN_RE.search(outbox.outbox[-1].text).group(1)  # type: ignore[union-attr]
    assert (await client.post("/api/auth/verify-email", json={"token": token})).status_code == 200
    # Token is single use.
    assert (await client.post("/api/auth/verify-email", json={"token": token})).status_code == 400
    me = (await client.get("/api/me")).json()
    assert me["email"] == "ana@example.com"
    assert me["email_verified"] is True
    assert (await client.post("/api/auth/logout")).status_code == 200
    assert (await client.get("/api/me")).status_code == 401
    r = await client.post("/api/auth/login", json={"email": "ana@example.com", "password": PW})
    assert r.status_code == 200
    assert "docify_session" in r.headers["set-cookie"]
    assert "HttpOnly" in r.headers["set-cookie"]
    assert (await client.get("/api/me")).status_code == 200


async def test_signup_no_enumeration(client: httpx.AsyncClient, outbox: MemorySender) -> None:
    await make_user(outbox, "bo@example.com")
    r = await client.post("/api/auth/signup", json={"email": "bo@example.com", "password": PW})
    assert r.status_code == 202  # same answer as a new signup
    assert outbox.outbox[-1].subject.startswith("Someone tried to sign up")


async def test_wrong_password_and_weak_password(client: httpx.AsyncClient, outbox: MemorySender) -> None:
    await make_user(outbox, "cy@example.com")
    r = await client.post("/api/auth/login", json={"email": "cy@example.com", "password": "wrong password!!"})
    assert r.status_code == 401
    r = await client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "wrong password!!"})
    assert r.status_code == 401
    r = await client.post("/api/auth/signup", json={"email": "dd@example.com", "password": "short"})
    assert r.status_code == 400
    assert r.json()["code"] == "weak_password"


async def test_login_rate_limit(client: httpx.AsyncClient, outbox: MemorySender) -> None:
    for _ in range(5):
        await client.post("/api/auth/login", json={"email": "x@example.com", "password": "nope nope nope"})
    r = await client.post("/api/auth/login", json={"email": "x@example.com", "password": "nope nope nope"})
    assert r.status_code == 429
    assert "retry-after" in r.headers


async def test_reset_password_kills_sessions(client: httpx.AsyncClient, outbox: MemorySender) -> None:
    c1 = await make_user(outbox, "ed@example.com")
    assert (await c1.get("/api/me")).status_code == 200
    assert (await client.post("/api/auth/forgot-password", json={"email": "ed@example.com"})).status_code == 202
    assert (await client.post("/api/auth/forgot-password", json={"email": "ghost@example.com"})).status_code == 202
    token = TOKEN_RE.search(outbox.outbox[-1].text).group(1)  # type: ignore[union-attr]
    r = await client.post("/api/auth/reset-password", json={"token": token, "password": "another strong pass 7"})
    assert r.status_code == 200
    assert (await c1.get("/api/me")).status_code == 401  # old session gone
    assert (await client.get("/api/me")).status_code == 200  # reset logs you in


async def test_csrf_header_required(outbox: MemorySender) -> None:
    from docify.api.app import create_app

    c = httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(start_background=False)),
                          base_url="http://testserver")
    r = await c.post("/api/auth/login", json={"email": "a@example.com", "password": PW})
    assert r.status_code == 403
    assert r.json()["code"] == "csrf"


async def test_sessions_list_and_revoke(client: httpx.AsyncClient, outbox: MemorySender) -> None:
    c1 = await make_user(outbox, "fi@example.com")
    r = await client.post("/api/auth/login", json={"email": "fi@example.com", "password": PW})
    assert r.status_code == 200
    sessions = (await c1.get("/api/me/sessions")).json()
    assert len(sessions) == 2
    other = next(s for s in sessions if not s["current"])
    assert (await c1.delete(f"/api/me/sessions/{other['id']}")).status_code == 200
    assert (await client.get("/api/me")).status_code == 401


async def test_change_password_signs_out_others(client: httpx.AsyncClient, outbox: MemorySender) -> None:
    c1 = await make_user(outbox, "gu@example.com")
    await client.post("/api/auth/login", json={"email": "gu@example.com", "password": PW})
    r = await c1.post("/api/me/password", json={"current_password": "bad", "new_password": "brand new pass 42"})
    assert r.status_code == 400
    r = await c1.post("/api/me/password", json={"current_password": PW, "new_password": "brand new pass 42"})
    assert r.status_code == 200
    assert (await c1.get("/api/me")).status_code == 200
    assert (await client.get("/api/me")).status_code == 401


# ----------------------------------------------------------------------------- OAuth


async def _github_login(client: httpx.AsyncClient, purpose: str = "login") -> httpx.Response:
    r = await client.get(f"/api/auth/github/start?purpose={purpose}")
    assert r.status_code == 302
    qs = parse_qs(urlparse(r.headers["location"]).query)
    assert qs["code_challenge_method"] == ["S256"]
    return await client.get(f"/api/auth/github/callback?code=abc&state={qs['state'][0]}")


async def test_github_login_creates_user(client: httpx.AsyncClient, gh: FakeGitHub) -> None:
    r = await _github_login(client)
    assert r.status_code == 302
    assert r.headers["location"] == "http://testserver/"
    me = (await client.get("/api/me")).json()
    assert me["email"] == "octo@example.com"
    assert me["identities"][0]["provider"] == "github"
    assert me["has_password"] is False


async def test_github_login_rejects_unverified_email(client: httpx.AsyncClient, gh: FakeGitHub) -> None:
    gh.emails = [{"email": "octo@example.com", "primary": True, "verified": False}]
    r = await _github_login(client)
    assert "error=provider_email_unverified" in r.headers["location"]


async def test_oauth_state_single_use_and_bound(client: httpx.AsyncClient, gh: FakeGitHub) -> None:
    r = await client.get("/api/auth/github/callback?code=abc&state=forged-state-value")
    assert "error=oauth_state" in r.headers["location"]


async def test_pre_account_takeover_defence(client: httpx.AsyncClient, outbox: MemorySender, gh: FakeGitHub) -> None:
    # Attacker registers the victim's email with a password but can't verify it.
    attacker = httpx.AsyncClient(transport=client._transport, base_url="http://testserver",  # type: ignore[attr-defined]
                                 headers={"X-Docify-CSRF": "1"})
    await attacker.post("/api/auth/signup", json={"email": "octo@example.com", "password": "attacker pass 123"})
    # Victim signs in with GitHub (verified email) → takes over, attacker's password is wiped.
    r = await _github_login(client)
    assert r.headers["location"] == "http://testserver/"
    async with session_scope() as db:
        user = (await db.execute(select(User).where(User.email == "octo@example.com"))).scalar_one()
        assert user.password_hash is None
        assert user.email_verified is True
    r = await attacker.post("/api/auth/login", json={"email": "octo@example.com", "password": "attacker pass 123"})
    assert r.status_code == 401


async def test_link_and_unlink(client: httpx.AsyncClient, outbox: MemorySender, gh: FakeGitHub) -> None:
    c = await make_user(outbox, "hana@example.com")
    gh.github_user = {"id": 4242, "login": "hana-gh", "name": "Hana", "avatar_url": None}
    gh.emails = [{"email": "other@example.com", "primary": True, "verified": True}]
    r = await _github_login(c, purpose="link")
    assert "linked=github" in r.headers["location"]
    me = (await c.get("/api/me")).json()
    assert [i["login"] for i in me["identities"]] == ["hana-gh"]
    # Same GitHub account can't be linked to a second user.
    c2 = await make_user(outbox, "ivo@example.com")
    r = await _github_login(c2, purpose="link")
    assert "error=identity_in_use" in r.headers["location"]
    # Unlinking works while a password exists.
    ident = me["identities"][0]["id"]
    assert (await c.delete(f"/api/me/identities/{ident}")).status_code == 200


async def test_cannot_unlink_last_login_method(client: httpx.AsyncClient, gh: FakeGitHub) -> None:
    await _github_login(client)
    me = (await client.get("/api/me")).json()
    r = await client.delete(f"/api/me/identities/{me['identities'][0]['id']}")
    assert r.status_code == 409
    assert r.json()["code"] == "last_login_method"


async def test_google_login_validates_id_token(client: httpx.AsyncClient) -> None:
    from cryptography.hazmat.primitives import serialization
    from jwt.algorithms import RSAAlgorithm

    from docify.auth import oauth

    oauth._jwks_cache = None
    key = serialization.load_pem_private_key(RSA_PRIVATE_PEM.encode(), password=None)
    jwk = RSAAlgorithm.to_jwk(key.public_key(), as_dict=True)  # type: ignore[arg-type]
    jwk.update({"kid": "k1", "alg": "RS256", "use": "sig"})
    r = await client.get("/api/auth/google/start")
    qs = parse_qs(urlparse(r.headers["location"]).query)
    claims = {"iss": "https://accounts.google.com", "aud": "google-client-id", "sub": "g-1",
              "email": "gina@example.com", "email_verified": True, "nonce": qs["nonce"][0],
              "exp": int(time.time()) + 300, "iat": int(time.time()), "name": "Gina"}
    id_token = jwt.encode(claims, RSA_PRIVATE_PEM, algorithm="RS256", headers={"kid": "k1"})
    with respx.mock(assert_all_called=False) as m:
        m.post(oauth.GOOGLE_TOKEN).mock(return_value=httpx.Response(200, json={"id_token": id_token}))
        m.get(oauth.GOOGLE_JWKS).mock(return_value=httpx.Response(200, json={"keys": [jwk]}))
        r = await client.get(f"/api/auth/google/callback?code=x&state={qs['state'][0]}")
    assert r.status_code == 302
    assert r.headers["location"] == "http://testserver/"
    assert (await client.get("/api/me")).json()["email"] == "gina@example.com"
    # Wrong nonce is rejected.
    r = await client.get("/api/auth/google/start")
    qs = parse_qs(urlparse(r.headers["location"]).query)
    bad = jwt.encode({**claims, "nonce": "other"}, RSA_PRIVATE_PEM, algorithm="RS256", headers={"kid": "k1"})
    with respx.mock(assert_all_called=False) as m:
        m.post(oauth.GOOGLE_TOKEN).mock(return_value=httpx.Response(200, json={"id_token": bad}))
        m.get(oauth.GOOGLE_JWKS).mock(return_value=httpx.Response(200, json={"keys": [jwk]}))
        r = await client.get(f"/api/auth/google/callback?code=x&state={qs['state'][0]}")
    assert "error=oauth_failed" in r.headers["location"]


async def test_account_delete(client: httpx.AsyncClient, outbox: MemorySender) -> None:
    c = await make_user(outbox, "jo@example.com")
    assert (await c.post("/api/workspaces", json={"name": "Solo"})).status_code == 201
    assert (await c.delete("/api/me")).status_code == 200
    async with session_scope() as db:
        assert (await db.execute(select(func.count()).select_from(User))).scalar_one() == 0
        assert (await db.execute(select(func.count()).select_from(Session))).scalar_one() == 0
        assert (await db.execute(select(func.count()).select_from(AuthIdentity))).scalar_one() == 0
