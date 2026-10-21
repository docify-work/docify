"""Request dependencies: DB session, principal, workspace access, `load_for_user` (§10.6).

Authorization rule of thumb: anything you can't see is a **404**, never a 403,
so ids don't leak the existence of other tenants' data.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Annotated, Any, TypeVar

import structlog
from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from docify.api.errors import Problem, not_found, unauthorized
from docify.auth.sessions import COOKIE, load_session
from docify.config import get_settings
from docify.db.models import Membership, Session, User, Workspace
from docify.db.session import session_factory

ROLE_RANK = {"member": 1, "admin": 2}


async def get_db() -> AsyncIterator[AsyncSession]:
    async with session_factory()() as db:
        try:
            yield db
            await db.commit()
        except BaseException:
            await db.rollback()
            raise


# scope="function": commit runs right after the endpoint returns and BEFORE the response is
# sent, so a client never sees "200 OK" for data that later failed to commit.
DB = Annotated[AsyncSession, Depends(get_db, scope="function")]


def client_ip(request: Request) -> str:
    """Viewer IP for rate limits.

    In the cloud we use `CloudFront-Viewer-Address` ("ip:port"), which CloudFront sets itself — the
    first X-Forwarded-For entry is client-controlled (CloudFront only *appends*), so trusting it would
    let anyone bypass per-IP limits (V25). The origin only accepts CloudFront traffic (SG + header).
    Locally (Vite proxy) X-Forwarded-For is fine.
    """
    viewer = request.headers.get("cloudfront-viewer-address")
    if viewer:
        return viewer.rsplit(":", 1)[0].strip("[]")[:64]
    if get_settings().is_local:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip()[:64]
    return request.client.host if request.client else "unknown"


@dataclass
class Principal:
    user: User | None
    session: Session | None
    ip: str
    memberships: dict[uuid.UUID, str] = field(default_factory=dict)

    @property
    def is_anonymous(self) -> bool:
        return self.user is None

    @property
    def user_id(self) -> uuid.UUID:
        if self.user is None:
            raise unauthorized()
        return self.user.id

    def role_in(self, workspace_id: uuid.UUID) -> str | None:
        return self.memberships.get(workspace_id)


async def current_principal(request: Request, db: DB) -> Principal:
    ip = client_ip(request)
    token = request.cookies.get(COOKIE)
    if not token:
        return Principal(None, None, ip)
    loaded = await load_session(db, token)
    if loaded is None:
        return Principal(None, None, ip)
    sess, user = loaded
    rows = (await db.execute(
        select(Membership.workspace_id, Membership.role)
        .join(Workspace, Workspace.id == Membership.workspace_id)
        .where(Membership.user_id == user.id, Workspace.deleted_at.is_(None))
    )).all()
    structlog.contextvars.bind_contextvars(user_id=str(user.id))
    return Principal(user, sess, ip, dict(rows))


CurrentPrincipal = Annotated[Principal, Depends(current_principal)]


async def require_user(principal: CurrentPrincipal) -> Principal:
    if principal.is_anonymous:
        raise unauthorized()
    return principal


UserPrincipal = Annotated[Principal, Depends(require_user)]


def has_role(principal: Principal, ws: Workspace, min_role: str | None) -> bool:
    """min_role None = read access (members, or anyone for the public demo workspace)."""
    role = principal.role_in(ws.id)
    if min_role is None:
        return role is not None or ws.is_public_demo
    return role is not None and ROLE_RANK[role] >= ROLE_RANK[min_role]


async def get_workspace(db: AsyncSession, principal: Principal, slug: str, min_role: str | None = None) -> Workspace:
    ws = (await db.execute(
        select(Workspace).where(Workspace.slug == slug, Workspace.deleted_at.is_(None))
    )).scalar_one_or_none()
    if ws is None or not has_role(principal, ws, min_role):
        if ws is not None and min_role is not None and principal.role_in(ws.id) is not None:
            raise Problem(403, "Forbidden", "Only workspace admins can do that.", code="admin_required")
        raise not_found("Workspace")
    if min_role is not None and principal.is_anonymous:
        raise unauthorized()
    structlog.contextvars.bind_contextvars(workspace_id=str(ws.id))
    return ws


M = TypeVar("M")


async def load_for_user(db: AsyncSession, model: type[M], obj_id: uuid.UUID, principal: Principal,
                        min_role: str | None = None) -> tuple[M, Workspace]:
    """Load a tenant row by id and check the principal can see its workspace. 404 otherwise."""
    m: Any = model
    row = (await db.execute(
        select(m, Workspace).join(Workspace, Workspace.id == m.workspace_id)
        .where(m.id == obj_id, Workspace.deleted_at.is_(None))
    )).first()
    if row is None:
        raise not_found(m.__name__)
    obj, ws = row
    if not has_role(principal, ws, min_role):
        if min_role is not None and principal.role_in(ws.id) is not None:
            raise Problem(403, "Forbidden", "Only workspace admins can do that.", code="admin_required")
        raise not_found(m.__name__)
    if min_role is not None and principal.is_anonymous:
        raise unauthorized()
    return obj, ws
