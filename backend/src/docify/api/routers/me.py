"""Current user: profile, identities, sessions, password, account deletion."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Response
from sqlalchemy import select

from docify.api.deps import DB, UserPrincipal
from docify.api.errors import not_found
from docify.api.schemas import ChangePasswordIn, IdentityOut, MembershipBrief, MeOut, Ok, PatchMeIn, SessionOut
from docify.auth import service
from docify.auth.sessions import clear_session_cookie
from docify.db.models import AuthIdentity, Membership, Session, Workspace
from docify.jobs import service as jobs
from docify.workspaces import purge_workspace

router = APIRouter(prefix="/me", tags=["account"])


async def _me(db: DB, principal: UserPrincipal) -> MeOut:
    user = principal.user
    assert user is not None
    identities = (await db.execute(select(AuthIdentity).where(AuthIdentity.user_id == user.id)
                                   .order_by(AuthIdentity.created_at))).scalars().all()
    rows = (await db.execute(
        select(Workspace, Membership.role).join(Membership, Membership.workspace_id == Workspace.id)
        .where(Membership.user_id == user.id, Workspace.deleted_at.is_(None)).order_by(Workspace.name)
    )).all()
    return MeOut(
        id=user.id, email=user.email, name=user.name, avatar_url=user.avatar_url, email_verified=user.email_verified,
        has_password=bool(user.password_hash),
        identities=[IdentityOut.model_validate(i) for i in identities],
        workspaces=[MembershipBrief(id=w.id, slug=w.slug, name=w.name, role=role, is_public_demo=w.is_public_demo)
                    for w, role in rows],
    )


@router.get("", response_model=MeOut)
async def get_me(db: DB, principal: UserPrincipal) -> MeOut:
    return await _me(db, principal)


@router.patch("", response_model=MeOut)
async def patch_me(body: PatchMeIn, db: DB, principal: UserPrincipal) -> MeOut:
    assert principal.user is not None
    if body.name is not None:
        principal.user.name = body.name.strip() or None
    return await _me(db, principal)


@router.delete("", response_model=Ok)
async def delete_me(db: DB, principal: UserPrincipal, response: Response) -> Ok:
    assert principal.user is not None
    solo = [ws for ws, role in principal.memberships.items() if role == "admin"]
    await service.delete_account(db, principal.user)
    # Workspaces that were deleted with the account → purge their repo data.
    job_ids = []
    for ws_id in solo:
        ws = await db.get(Workspace, ws_id)
        if ws is not None and ws.deleted_at is not None:
            job_ids += await purge_workspace(db, ws)
    await db.commit()
    await jobs.dispatch(job_ids)
    clear_session_cookie(response)
    return Ok(message="Your account was deleted.")


@router.post("/password", response_model=Ok)
async def change_password(body: ChangePasswordIn, db: DB, principal: UserPrincipal) -> Ok:
    assert principal.user is not None and principal.session is not None
    await service.change_password(db, principal.user, body.current_password, body.new_password, principal.session.id)
    return Ok(message="Password updated. Other sessions were signed out.")


@router.get("/identities", response_model=list[IdentityOut])
async def identities(db: DB, principal: UserPrincipal) -> list[IdentityOut]:
    rows = (await db.execute(select(AuthIdentity).where(AuthIdentity.user_id == principal.user_id))).scalars().all()
    return [IdentityOut.model_validate(r) for r in rows]


@router.delete("/identities/{identity_id}", response_model=Ok)
async def unlink(identity_id: uuid.UUID, db: DB, principal: UserPrincipal) -> Ok:
    assert principal.user is not None
    await service.unlink_identity(db, principal.user, identity_id)
    return Ok()


@router.get("/sessions", response_model=list[SessionOut])
async def sessions(db: DB, principal: UserPrincipal) -> list[SessionOut]:
    rows = (await db.execute(select(Session).where(Session.user_id == principal.user_id)
                             .order_by(Session.last_seen_at.desc()))).scalars().all()
    current = principal.session.id if principal.session else None
    return [SessionOut(id=s.id, created_at=s.created_at, last_seen_at=s.last_seen_at, ip=s.ip,
                       user_agent=s.user_agent, current=s.id == current) for s in rows]


@router.delete("/sessions/{session_id}", response_model=Ok)
async def revoke_session(session_id: uuid.UUID, db: DB, principal: UserPrincipal) -> Ok:
    sess = (await db.execute(select(Session).where(Session.id == session_id, Session.user_id == principal.user_id))) \
        .scalar_one_or_none()
    if sess is None:
        raise not_found("Session")
    await db.delete(sess)
    return Ok()
