"""Account flows: email+password, verification, reset, identity resolution & linking.

Security rules (Master Doc §10.3–10.4):
- No user enumeration: signup / forgot-password always answer the same way.
- Login requires a verified email.
- OAuth identity resolution with the *pre-account takeover* defence: an unverified
  password account for the same email is taken over (password wiped, sessions killed).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from docify.api.errors import Problem, bad_request, conflict
from docify.audit import audit
from docify.auth.oauth import ProviderProfile
from docify.auth.passwords import PasswordRuleError, ahash_password, averify_password, check_password_rules
from docify.auth.sessions import delete_user_sessions
from docify.auth.tokens import new_token, token_hmac
from docify.db.models import AuthIdentity, EmailToken, Membership, User, Workspace
from docify.email import templates
from docify.email.sender import send_in_background
from docify.observability.metrics import AUTH_EVENTS

VERIFY_TTL = timedelta(hours=24)
RESET_TTL = timedelta(hours=1)


def _now() -> datetime:
    return datetime.now(UTC)


def normalize_email(email: str) -> str:
    return email.strip().lower()


async def _issue_email_token(db: AsyncSession, user: User, purpose: str, ttl: timedelta,
                             password_hash: str | None = None) -> str:
    # Only one live token per purpose: older ones stop working.
    await db.execute(delete(EmailToken).where(EmailToken.user_id == user.id, EmailToken.purpose == purpose,
                                              EmailToken.used_at.is_(None)))
    token = new_token()
    db.add(EmailToken(user_id=user.id, purpose=purpose, token_hmac=token_hmac(token), expires_at=_now() + ttl,
                      password_hash=password_hash))
    await db.flush()
    return token


async def _consume_email_token(db: AsyncSession, token: str, purpose: str) -> tuple[User, EmailToken]:
    row = (await db.execute(
        select(EmailToken, User).join(User, User.id == EmailToken.user_id)
        .where(EmailToken.token_hmac == token_hmac(token), EmailToken.purpose == purpose)
        .with_for_update(of=EmailToken)
    )).first()
    if row is None or row[0].used_at is not None or row[0].expires_at <= _now():
        raise bad_request("This link is invalid or has expired.", code="invalid_token")
    row[0].used_at = _now()
    return row[1], row[0]


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    return (await db.execute(select(User).where(User.email == normalize_email(email)))).scalar_one_or_none()


# ----------------------------------------------------------------------------- email + password


async def signup(db: AsyncSession, email: str, password: str, name: str | None) -> None:
    email = normalize_email(email)
    try:
        check_password_rules(password, email=email)
    except PasswordRuleError as exc:
        raise bad_request(str(exc), code="weak_password") from exc
    # Always hash: same cost on every path, so response time doesn't reveal whether the email exists.
    pw_hash = await ahash_password(password)
    existing = await get_user_by_email(db, email)
    if existing is not None:
        # Same response as a new signup; tell the real owner instead (no enumeration).
        if existing.email_verified:
            send_in_background(templates.signup_notice(email))
        else:
            # Unverified: the new link carries THIS signup's password. Whoever opens it (the mailbox
            # owner) gets their own password; a stranger's earlier password is discarded (F53).
            token = await _issue_email_token(db, existing, "verify", VERIFY_TTL, password_hash=pw_hash)
            send_in_background(templates.verify_email(email, token))
        AUTH_EVENTS.labels("signup", "existing").inc()
        return
    user = User(email=email, name=(name or "").strip()[:200] or None)
    db.add(user)
    await db.flush()
    token = await _issue_email_token(db, user, "verify", VERIFY_TTL, password_hash=pw_hash)
    audit(db, "user.signup", actor=user.id)
    send_in_background(templates.verify_email(email, token))
    AUTH_EVENTS.labels("signup", "created").inc()


async def verify_email(db: AsyncSession, token: str) -> User:
    user, tok = await _consume_email_token(db, token, "verify")
    if not user.email_verified:
        # The password comes only from the link that was opened. A link without one (resend) leaves the
        # account password-less: the user is signed in by this request and can set one in Account.
        user.password_hash = tok.password_hash
        user.session_gen += 1
        await delete_user_sessions(db, user.id)
    user.email_verified = True
    audit(db, "user.email_verified", actor=user.id)
    return user


async def resend_verification(db: AsyncSession, email: str) -> None:
    user = await get_user_by_email(db, email)
    if user is not None and not user.email_verified:
        token = await _issue_email_token(db, user, "verify", VERIFY_TTL)
        send_in_background(templates.verify_email(user.email, token))


async def login_password(db: AsyncSession, email: str, password: str) -> User:
    user = await get_user_by_email(db, email)
    candidate = user.password_hash if user else None
    if user is not None and not user.email_verified:
        # Unverified accounts keep the chosen password on the pending verify link (see signup).
        candidate = (await db.execute(select(EmailToken.password_hash).where(
            EmailToken.user_id == user.id, EmailToken.purpose == "verify", EmailToken.used_at.is_(None))
            .order_by(EmailToken.created_at.desc()).limit(1))).scalar_one_or_none()
    ok = await averify_password(password, candidate)
    if user is None or not ok or user.disabled:
        AUTH_EVENTS.labels("login", "failed").inc()
        raise Problem(401, "Unauthorized", "Wrong email or password.", code="invalid_credentials")
    if not user.email_verified:
        AUTH_EVENTS.labels("login", "unverified").inc()
        raise Problem(403, "Forbidden", "Please verify your email first. Check your inbox.",
                      code="email_not_verified")
    AUTH_EVENTS.labels("login", "ok").inc()
    return user


async def forgot_password(db: AsyncSession, email: str) -> None:
    user = await get_user_by_email(db, email)
    if user is None or user.disabled:
        return
    token = await _issue_email_token(db, user, "reset", RESET_TTL)
    send_in_background(templates.reset_password(user.email, token))


async def reset_password(db: AsyncSession, token: str, password: str) -> User:
    user, _ = await _consume_email_token(db, token, "reset")
    try:
        check_password_rules(password, email=user.email)
    except PasswordRuleError as exc:
        raise bad_request(str(exc), code="weak_password") from exc
    user.password_hash = await ahash_password(password)
    # The reset link proves mailbox ownership, so the email is now verified too.
    user.email_verified = True
    user.session_gen += 1
    await delete_user_sessions(db, user.id)
    audit(db, "user.password_reset", actor=user.id)
    return user


async def change_password(db: AsyncSession, user: User, current: str | None, new: str,
                          keep_session_id: uuid.UUID | None) -> None:
    if user.password_hash and not await averify_password(current or "", user.password_hash):
        raise Problem(400, "Bad request", "Current password is wrong.", code="invalid_credentials")
    try:
        check_password_rules(new, email=user.email)
    except PasswordRuleError as exc:
        raise bad_request(str(exc), code="weak_password") from exc
    user.password_hash = await ahash_password(new)
    await delete_user_sessions(db, user.id, except_id=keep_session_id)
    audit(db, "user.password_changed", actor=user.id)


# ----------------------------------------------------------------------------- OAuth identities


async def resolve_oauth_login(db: AsyncSession, profile: ProviderProfile) -> User:
    """§10.4 identity resolution for purpose=login."""
    ident = (await db.execute(select(AuthIdentity).where(
        AuthIdentity.provider == profile.provider, AuthIdentity.provider_user_id == profile.provider_user_id
    ))).scalar_one_or_none()
    if ident is not None:
        user = await db.get(User, ident.user_id)
        assert user is not None
        if user.disabled:
            raise Problem(403, "Forbidden", "This account is disabled.", code="disabled")
        ident.email, ident.email_verified, ident.login = profile.email, profile.email_verified, profile.login
        return user

    if not profile.email or not profile.email_verified:
        AUTH_EVENTS.labels(f"oauth_{profile.provider}", "unverified_email").inc()
        raise Problem(403, "Forbidden",
                      f"Your {profile.provider.title()} account has no verified primary email. "
                      "Verify it there, or sign up with email and password.", code="provider_email_unverified")

    user = await get_user_by_email(db, profile.email)
    if user is None:
        user = User(email=normalize_email(profile.email), email_verified=True, name=profile.name,
                    avatar_url=profile.avatar_url)
        db.add(user)
        await db.flush()
        audit(db, "user.signup_oauth", actor=user.id, provider=profile.provider)
    elif not user.email_verified:
        # Pre-account takeover defence: someone may have registered this email with a password
        # they control. The verified provider proves ownership, so wipe their foothold.
        user.password_hash = None
        user.email_verified = True
        user.session_gen += 1
        await delete_user_sessions(db, user.id)
        await db.execute(delete(EmailToken).where(EmailToken.user_id == user.id))
        audit(db, "user.unverified_takeover", actor=user.id, provider=profile.provider)
    if user.disabled:
        raise Problem(403, "Forbidden", "This account is disabled.", code="disabled")
    if not user.avatar_url and profile.avatar_url:
        user.avatar_url = profile.avatar_url
    if not user.name and profile.name:
        user.name = profile.name
    db.add(AuthIdentity(user_id=user.id, provider=profile.provider, provider_user_id=profile.provider_user_id,
                        email=profile.email, email_verified=profile.email_verified, login=profile.login))
    await db.flush()
    AUTH_EVENTS.labels(f"oauth_{profile.provider}", "ok").inc()
    return user


async def link_identity(db: AsyncSession, user: User, profile: ProviderProfile) -> None:
    ident = (await db.execute(select(AuthIdentity).where(
        AuthIdentity.provider == profile.provider, AuthIdentity.provider_user_id == profile.provider_user_id
    ))).scalar_one_or_none()
    if ident is not None:
        if ident.user_id != user.id:
            raise conflict(f"This {profile.provider.title()} account is linked to another Docify user.",
                           code="identity_in_use")
        return
    existing_same_provider = (await db.execute(select(AuthIdentity).where(
        AuthIdentity.user_id == user.id, AuthIdentity.provider == profile.provider
    ))).scalar_one_or_none()
    if existing_same_provider is not None:
        raise conflict(f"You already linked a {profile.provider.title()} account. Unlink it first.",
                       code="provider_already_linked")
    db.add(AuthIdentity(user_id=user.id, provider=profile.provider, provider_user_id=profile.provider_user_id,
                        email=profile.email, email_verified=profile.email_verified, login=profile.login))
    audit(db, "user.identity_linked", actor=user.id, provider=profile.provider)


async def unlink_identity(db: AsyncSession, user: User, identity_id: uuid.UUID) -> None:
    ident = (await db.execute(select(AuthIdentity).where(
        AuthIdentity.id == identity_id, AuthIdentity.user_id == user.id
    ))).scalar_one_or_none()
    if ident is None:
        raise Problem(404, "Not found", "Identity not found.", code="not_found")
    count = (await db.execute(select(func.count()).select_from(AuthIdentity)
                              .where(AuthIdentity.user_id == user.id))).scalar_one()
    if count <= 1 and not user.password_hash:
        raise conflict("You can't remove your only way to sign in. Set a password first.", code="last_login_method")
    await db.delete(ident)
    audit(db, "user.identity_unlinked", actor=user.id, provider=ident.provider)


# ----------------------------------------------------------------------------- account deletion


async def delete_account(db: AsyncSession, user: User) -> None:
    """§10.6: blocked while the user is the only admin of a workspace that has other members."""
    admin_ws = (await db.execute(
        select(Membership.workspace_id).join(Workspace, Workspace.id == Membership.workspace_id)
        .where(Membership.user_id == user.id, Membership.role == "admin", Workspace.deleted_at.is_(None))
    )).scalars().all()
    for ws_id in admin_ws:
        others = (await db.execute(select(func.count()).select_from(Membership).where(
            Membership.workspace_id == ws_id, Membership.user_id != user.id))).scalar_one()
        other_admins = (await db.execute(select(func.count()).select_from(Membership).where(
            Membership.workspace_id == ws_id, Membership.user_id != user.id, Membership.role == "admin"))).scalar_one()
        if others > 0 and other_admins == 0:
            raise conflict("You are the only admin of a workspace with other members. "
                           "Make someone else admin or delete the workspace first.", code="sole_admin")
        if others == 0:
            # Solo workspace: delete it with the account (repo data purged by the worker).
            await db.execute(update(Workspace).where(Workspace.id == ws_id).values(deleted_at=_now()))
    audit(db, "user.deleted", actor=None, target=str(user.id))
    await db.delete(user)
