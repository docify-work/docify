"""Server-side sessions (D20): opaque cookie, HMAC stored in DB, sliding + absolute expiry."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from docify.auth.tokens import new_token, token_hmac
from docify.config import get_settings
from docify.db.models import Session, User

COOKIE = "docify_session"
SLIDE_EVERY = timedelta(minutes=10)


def now() -> datetime:
    return datetime.now(UTC)


async def create_session(db: AsyncSession, user: User, *, ip: str | None, user_agent: str | None) -> str:
    s = get_settings()
    token = new_token()
    t = now()
    db.add(Session(
        user_id=user.id, token_hmac=token_hmac(token),
        expires_at=t + timedelta(days=s.session_days),
        absolute_expires_at=t + timedelta(days=s.session_absolute_days),
        last_seen_at=t, ip=ip, user_agent=(user_agent or "")[:300] or None,
    ))
    user.last_login_at = t
    await db.flush()
    return token


async def load_session(db: AsyncSession, token: str) -> tuple[Session, User] | None:
    row = (await db.execute(
        select(Session, User).join(User, User.id == Session.user_id).where(Session.token_hmac == token_hmac(token))
    )).first()
    if row is None:
        return None
    sess, user = row
    t = now()
    if sess.expires_at <= t or sess.absolute_expires_at <= t or user.disabled:
        await db.delete(sess)
        return None
    if t - sess.last_seen_at >= SLIDE_EVERY:  # sliding window, at most one write per 10 min
        sess.last_seen_at = t
        sess.expires_at = min(t + timedelta(days=get_settings().session_days), sess.absolute_expires_at)
    return sess, user


async def delete_user_sessions(db: AsyncSession, user_id: uuid.UUID, *, except_id: uuid.UUID | None = None) -> None:
    stmt = delete(Session).where(Session.user_id == user_id)
    if except_id is not None:
        stmt = stmt.where(Session.id != except_id)
    await db.execute(stmt)


def set_session_cookie(response: Response, token: str) -> None:
    s = get_settings()
    response.set_cookie(
        COOKIE, token, max_age=s.session_absolute_days * 86400, httponly=True,
        secure=s.cookie_secure, samesite="lax", path="/",
    )


def clear_session_cookie(response: Response) -> None:
    s = get_settings()
    response.delete_cookie(COOKIE, path="/", httponly=True, secure=s.cookie_secure, samesite="lax")
