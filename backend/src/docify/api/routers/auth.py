"""Auth endpoints: email+password, verification, reset, OAuth (GitHub/Google) login & linking (§10)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select

from docify.api.deps import DB, CurrentPrincipal, client_ip
from docify.api.errors import Problem, bad_request
from docify.api.schemas import EmailIn, LoginIn, Ok, ResetPasswordIn, SignupIn, TokenIn
from docify.auth import oauth, service
from docify.auth.sessions import clear_session_cookie, create_session, set_session_cookie
from docify.auth.tokens import new_token, token_hmac
from docify.cache import hit
from docify.config import get_settings
from docify.db.models import OAuthState, Session
from docify.observability.logging import get_logger

router = APIRouter(prefix="/auth", tags=["auth"])
log = get_logger(__name__)
STATE_TTL = timedelta(minutes=10)
CHECK_EMAIL = "If that address can be used, we've sent an email. Check your inbox."


def _safe_redirect(path: str | None, default: str = "/") -> str:
    if not path or not path.startswith("/") or path.startswith("//") or "\\" in path:
        return default
    return path[:300]


def _front(path: str) -> str:
    return get_settings().public_base_url.rstrip("/") + path


@router.post("/signup", response_model=Ok, status_code=202)
async def signup(body: SignupIn, request: Request, db: DB) -> Ok:
    await hit(f"signup:ip:{client_ip(request)}", limit=5, window_s=3600)
    await service.signup(db, body.email, body.password, body.name)
    return Ok(message=CHECK_EMAIL)


@router.post("/verify-email", response_model=Ok)
async def verify_email(body: TokenIn, request: Request, response: Response, db: DB) -> Ok:
    user = await service.verify_email(db, body.token)
    # Verifying proves mailbox ownership → sign the user in directly.
    token = await create_session(db, user, ip=client_ip(request), user_agent=request.headers.get("user-agent"))
    set_session_cookie(response, token)
    return Ok(message="Email verified.")


@router.post("/resend-verification", response_model=Ok, status_code=202)
async def resend(body: EmailIn, db: DB) -> Ok:
    await hit(f"resend:{body.email.lower()}", limit=3, window_s=3600)
    await service.resend_verification(db, body.email)
    return Ok(message=CHECK_EMAIL)


@router.post("/login", response_model=Ok)
async def login(body: LoginIn, request: Request, response: Response, db: DB) -> Ok:
    ip = client_ip(request)
    await hit(f"login:ip:{ip}", limit=20, window_s=3600)
    await hit(f"login:ipmail:{ip}:{body.email.lower()}", limit=5, window_s=60)
    user = await service.login_password(db, body.email, body.password)
    token = await create_session(db, user, ip=ip, user_agent=request.headers.get("user-agent"))
    set_session_cookie(response, token)
    return Ok()


@router.post("/logout", response_model=Ok)
async def logout(principal: CurrentPrincipal, response: Response, db: DB) -> Ok:
    if principal.session is not None:
        await db.delete(principal.session)
    clear_session_cookie(response)
    return Ok()


@router.post("/forgot-password", response_model=Ok, status_code=202)
async def forgot(body: EmailIn, request: Request, db: DB) -> Ok:
    await hit(f"reset:{body.email.lower()}", limit=3, window_s=3600)
    await hit(f"reset:ip:{client_ip(request)}", limit=10, window_s=3600)
    await service.forgot_password(db, body.email)
    return Ok(message=CHECK_EMAIL)


@router.post("/reset-password", response_model=Ok)
async def reset(body: ResetPasswordIn, request: Request, response: Response, db: DB) -> Ok:
    user = await service.reset_password(db, body.token, body.password)
    token = await create_session(db, user, ip=client_ip(request), user_agent=request.headers.get("user-agent"))
    set_session_cookie(response, token)
    return Ok(message="Password updated.")


# ----------------------------------------------------------------------------- OAuth


async def new_oauth_state(db: DB, *, provider: str, purpose: str, session: Session | None,
                          workspace_id: object = None, redirect_to: str | None = None) -> tuple[str, str, str]:
    """Returns (state, code_challenge, nonce)."""
    state = new_token(24)
    verifier, challenge = oauth.pkce_pair()
    nonce = new_token(16)
    db.add(OAuthState(state_hmac=token_hmac(state), provider=provider, purpose=purpose,
                      session_id=session.id if session else None, workspace_id=workspace_id,
                      code_verifier=verifier, nonce=nonce, redirect_to=redirect_to,
                      expires_at=datetime.now(UTC) + STATE_TTL))
    await db.flush()
    return state, challenge, nonce


@router.get("/{provider}/start", summary="Begin OAuth login or account linking (browser redirect)")
async def oauth_start(provider: Literal["github", "google"], principal: CurrentPrincipal, request: Request, db: DB,
                      purpose: Literal["login", "link"] = "login",
                      redirect_to: str | None = Query(default=None, max_length=300)) -> RedirectResponse:
    s = get_settings()
    if (provider == "github" and not s.github_configured) or (provider == "google" and not s.google_configured):
        return RedirectResponse(_front("/login?error=provider_disabled"), status_code=302)
    await hit(f"oauth:ip:{client_ip(request)}", limit=30, window_s=600)
    if purpose == "link" and principal.is_anonymous:
        return RedirectResponse(_front("/login?error=login_required"), status_code=302)
    default = "/account" if purpose == "link" else "/"
    state, challenge, nonce = await new_oauth_state(
        db, provider=provider, purpose=purpose, session=principal.session,
        redirect_to=_safe_redirect(redirect_to, default))
    url = oauth.github_authorize_url(state, challenge) if provider == "github" \
        else oauth.google_authorize_url(state, challenge, nonce)
    return RedirectResponse(url, status_code=302)


@router.get("/{provider}/callback", summary="OAuth redirect target")
async def oauth_callback(provider: Literal["github", "google"], principal: CurrentPrincipal, request: Request,
                         response: Response, db: DB, code: str | None = None, state: str | None = None,
                         error: str | None = None) -> RedirectResponse:
    from docify.api.routers.github import complete_install

    if error or not code or not state:
        return RedirectResponse(_front("/login?error=oauth_cancelled"), status_code=302)
    row = (await db.execute(select(OAuthState).where(OAuthState.state_hmac == token_hmac(state))
                            .with_for_update())).scalar_one_or_none()
    if row is None or row.provider != provider or row.expires_at <= datetime.now(UTC):
        return RedirectResponse(_front("/login?error=oauth_state"), status_code=302)
    await db.delete(row)  # single use
    # States created by a signed-in user only complete in that same session (login CSRF defence).
    if row.session_id is not None and (principal.session is None or principal.session.id != row.session_id):
        return RedirectResponse(_front("/login?error=oauth_session"), status_code=302)
    try:
        profile = await oauth.github_exchange(code, row.code_verifier) if provider == "github" \
            else await oauth.google_exchange(code, row.code_verifier, row.nonce)
    except oauth.OAuthError as exc:
        log.info("oauth.exchange_failed", provider=provider, error=str(exc))
        return RedirectResponse(_front("/login?error=oauth_failed"), status_code=302)

    try:
        if row.purpose == "install":
            dest = await complete_install(db, principal, row, profile)
            return RedirectResponse(_front(dest), status_code=302)
        if row.purpose == "link":
            if principal.user is None:
                return RedirectResponse(_front("/login?error=login_required"), status_code=302)
            await service.link_identity(db, principal.user, profile)
            return RedirectResponse(_front(_safe_redirect(row.redirect_to, "/account") + "?linked=" + provider),
                                    status_code=302)
        user = await service.resolve_oauth_login(db, profile)
    except Problem as exc:
        await db.commit()  # keep the deleted state row / audit
        return RedirectResponse(_front(f"/login?error={quote(exc.code)}"), status_code=302)

    if principal.session is not None:
        await db.delete(principal.session)  # rotate session on login
    token = await create_session(db, user, ip=client_ip(request), user_agent=request.headers.get("user-agent"))
    redirect = RedirectResponse(_front(_safe_redirect(row.redirect_to)), status_code=302)
    set_session_cookie(redirect, token)
    return redirect


def require_provider(provider: str) -> None:
    if provider not in ("github", "google"):
        raise bad_request("Unknown provider.")
