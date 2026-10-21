"""Workspaces, members, invites (§10.6 rules: last admin protection, verified-email invites)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter
from sqlalchemy import func, select

from docify.api.deps import DB, CurrentPrincipal, UserPrincipal, get_workspace
from docify.api.errors import Problem, bad_request, conflict, not_found
from docify.api.schemas import (
    InviteIn,
    InviteOut,
    InvitePublicOut,
    MemberOut,
    MemberPatch,
    Ok,
    WorkspaceIn,
    WorkspaceOut,
    WorkspacePatch,
    WorkspaceSettings,
)
from docify.audit import audit
from docify.auth.tokens import new_token, token_hmac
from docify.cache import hit
from docify.db.models import Invite, Membership, Repository, User, Workspace
from docify.email import templates
from docify.email.sender import send_safely
from docify.jobs import service as jobs
from docify.workspaces import purge_workspace, slugify, unique_slug

router = APIRouter(tags=["workspaces"])
INVITE_TTL = timedelta(days=7)
MAX_WORKSPACES_PER_USER = 10


async def _out(db: DB, ws: Workspace, role: str | None) -> WorkspaceOut:
    repos = (await db.execute(select(func.count()).select_from(Repository).where(
        Repository.workspace_id == ws.id, Repository.status != "disconnected"))).scalar_one()
    members = (await db.execute(select(func.count()).select_from(Membership)
                                .where(Membership.workspace_id == ws.id))).scalar_one()
    return WorkspaceOut(id=ws.id, slug=ws.slug, name=ws.name, role=role, is_public_demo=ws.is_public_demo,
                        settings=WorkspaceSettings(**(ws.settings or {})), created_at=ws.created_at,
                        repo_count=repos, member_count=members)


@router.get("/workspaces", response_model=list[WorkspaceOut])
async def list_workspaces(db: DB, principal: UserPrincipal) -> list[WorkspaceOut]:
    if not principal.memberships:
        return []
    rows = (await db.execute(select(Workspace).where(Workspace.id.in_(list(principal.memberships)),
                                                     Workspace.deleted_at.is_(None)).order_by(Workspace.name))).scalars()
    return [await _out(db, ws, principal.role_in(ws.id)) for ws in rows]


@router.post("/workspaces", response_model=WorkspaceOut, status_code=201)
async def create_workspace(body: WorkspaceIn, db: DB, principal: UserPrincipal) -> WorkspaceOut:
    assert principal.user is not None
    if not principal.user.email_verified:
        raise Problem(403, "Forbidden", "Verify your email first.", code="email_not_verified")
    if len(principal.memberships) >= MAX_WORKSPACES_PER_USER:
        raise conflict("You've reached the workspace limit.", code="workspace_limit")
    slug = body.slug or slugify(body.name)
    if body.slug:
        taken = (await db.execute(select(func.count()).select_from(Workspace).where(Workspace.slug == slug)))\
            .scalar_one()
        if taken:
            raise conflict("That workspace URL is taken.", code="slug_taken")
    else:
        slug = await unique_slug(db, slug)
    ws = Workspace(slug=slug, name=body.name.strip())
    db.add(ws)
    await db.flush()
    db.add(Membership(workspace_id=ws.id, user_id=principal.user.id, role="admin"))
    audit(db, "workspace.created", actor=principal.user.id, workspace_id=ws.id)
    await db.flush()
    await db.refresh(ws)
    return await _out(db, ws, "admin")


@router.get("/workspaces/{ws}", response_model=WorkspaceOut)
async def get_ws(ws: str, db: DB, principal: CurrentPrincipal) -> WorkspaceOut:
    w = await get_workspace(db, principal, ws)
    return await _out(db, w, principal.role_in(w.id))


@router.patch("/workspaces/{ws}", response_model=WorkspaceOut)
async def patch_ws(ws: str, body: WorkspacePatch, db: DB, principal: UserPrincipal) -> WorkspaceOut:
    w = await get_workspace(db, principal, ws, "admin")
    if body.name is not None:
        w.name = body.name.strip()
    if body.settings is not None:
        new = dict(w.settings or {})
        new.update(body.settings.model_dump(exclude_none=True))
        w.settings = new
    audit(db, "workspace.updated", actor=principal.user_id, workspace_id=w.id,
          changes=body.model_dump(exclude_none=True))
    return await _out(db, w, "admin")


@router.delete("/workspaces/{ws}", response_model=Ok)
async def delete_ws(ws: str, db: DB, principal: UserPrincipal) -> Ok:
    w = await get_workspace(db, principal, ws, "admin")
    if w.is_public_demo:
        raise bad_request("The demo workspace can't be deleted here.")
    w.deleted_at = datetime.now(UTC)
    w.slug = f"{w.slug}-deleted-{uuid.uuid4().hex[:6]}"[:60]  # free the slug
    job_ids = await purge_workspace(db, w)
    audit(db, "workspace.deleted", actor=principal.user_id, workspace_id=w.id)
    await db.commit()
    await jobs.dispatch(job_ids)
    return Ok(message="Workspace deleted.")


# ----------------------------------------------------------------------------- members


@router.get("/workspaces/{ws}/members", response_model=list[MemberOut])
async def members(ws: str, db: DB, principal: UserPrincipal) -> list[MemberOut]:
    w = await get_workspace(db, principal, ws, "member")
    rows = (await db.execute(select(Membership, User).join(User, User.id == Membership.user_id)
                             .where(Membership.workspace_id == w.id).order_by(Membership.created_at))).all()
    return [MemberOut(user_id=u.id, email=u.email, name=u.name, avatar_url=u.avatar_url, role=m.role,
                      joined_at=m.created_at) for m, u in rows]


async def _admin_count(db: DB, ws_id: uuid.UUID) -> int:
    return int((await db.execute(select(func.count()).select_from(Membership).where(
        Membership.workspace_id == ws_id, Membership.role == "admin"))).scalar_one())


async def _membership(db: DB, ws_id: uuid.UUID, user_id: uuid.UUID) -> Membership:
    m = (await db.execute(select(Membership).where(Membership.workspace_id == ws_id, Membership.user_id == user_id)
                          .with_for_update())).scalar_one_or_none()
    if m is None:
        raise not_found("Member")
    return m


@router.patch("/workspaces/{ws}/members/{user_id}", response_model=Ok)
async def change_role(ws: str, user_id: uuid.UUID, body: MemberPatch, db: DB, principal: UserPrincipal) -> Ok:
    w = await get_workspace(db, principal, ws, "admin")
    m = await _membership(db, w.id, user_id)
    if m.role == "admin" and body.role != "admin" and await _admin_count(db, w.id) <= 1:
        raise conflict("A workspace needs at least one admin.", code="last_admin")
    m.role = body.role
    audit(db, "member.role_changed", actor=principal.user_id, workspace_id=w.id, target=str(user_id), role=body.role)
    return Ok()


@router.delete("/workspaces/{ws}/members/{user_id}", response_model=Ok)
async def remove_member(ws: str, user_id: uuid.UUID, db: DB, principal: UserPrincipal) -> Ok:
    w = await get_workspace(db, principal, ws, "admin")
    m = await _membership(db, w.id, user_id)
    if m.role == "admin" and await _admin_count(db, w.id) <= 1:
        raise conflict("A workspace needs at least one admin.", code="last_admin")
    await db.delete(m)
    audit(db, "member.removed", actor=principal.user_id, workspace_id=w.id, target=str(user_id))
    return Ok()


@router.post("/workspaces/{ws}/leave", response_model=Ok)
async def leave(ws: str, db: DB, principal: UserPrincipal) -> Ok:
    w = await get_workspace(db, principal, ws, "member")
    m = await _membership(db, w.id, principal.user_id)
    if m.role == "admin" and await _admin_count(db, w.id) <= 1:
        raise conflict("You are the last admin. Make someone else admin or delete the workspace.", code="last_admin")
    await db.delete(m)
    return Ok()


# ----------------------------------------------------------------------------- invites


@router.get("/workspaces/{ws}/invites", response_model=list[InviteOut])
async def list_invites(ws: str, db: DB, principal: UserPrincipal) -> list[InviteOut]:
    w = await get_workspace(db, principal, ws, "admin")
    rows = (await db.execute(select(Invite).where(Invite.workspace_id == w.id, Invite.accepted_at.is_(None),
                                                  Invite.revoked_at.is_(None)).order_by(Invite.created_at.desc())))
    return [InviteOut.model_validate(i) for i in rows.scalars()]


@router.post("/workspaces/{ws}/invites", response_model=InviteOut, status_code=201)
async def create_invite(ws: str, body: InviteIn, db: DB, principal: UserPrincipal) -> InviteOut:
    w = await get_workspace(db, principal, ws, "admin")
    assert principal.user is not None
    await hit(f"invite:{w.id}", limit=30, window_s=3600)
    email = body.email.lower()
    already = (await db.execute(select(func.count()).select_from(Membership).join(User, User.id == Membership.user_id)
                                .where(Membership.workspace_id == w.id, User.email == email))).scalar_one()
    if already:
        raise conflict("That person is already a member.", code="already_member")
    # Re-inviting replaces the previous open invite (new token, new expiry).
    old = (await db.execute(select(Invite).where(Invite.workspace_id == w.id, Invite.email == email,
                                                 Invite.accepted_at.is_(None), Invite.revoked_at.is_(None))))\
        .scalar_one_or_none()
    if old is not None:
        old.revoked_at = datetime.now(UTC)
        await db.flush()
    token = new_token()
    inv = Invite(workspace_id=w.id, email=email, role=body.role, token_hmac=token_hmac(token),
                 invited_by=principal.user.id, expires_at=datetime.now(UTC) + INVITE_TTL)
    db.add(inv)
    await db.flush()
    await db.refresh(inv)
    audit(db, "invite.created", actor=principal.user.id, workspace_id=w.id, target=email, role=body.role)
    await send_safely(templates.invite(email, token, w.name, principal.user.name or principal.user.email))
    return InviteOut.model_validate(inv)


@router.delete("/workspaces/{ws}/invites/{invite_id}", response_model=Ok)
async def revoke_invite(ws: str, invite_id: uuid.UUID, db: DB, principal: UserPrincipal) -> Ok:
    w = await get_workspace(db, principal, ws, "admin")
    inv = (await db.execute(select(Invite).where(Invite.id == invite_id, Invite.workspace_id == w.id)))\
        .scalar_one_or_none()
    if inv is None:
        raise not_found("Invite")
    inv.revoked_at = datetime.now(UTC)
    return Ok()


async def _invite_by_token(db: DB, token: str) -> tuple[Invite, Workspace]:
    row = (await db.execute(select(Invite, Workspace).join(Workspace, Workspace.id == Invite.workspace_id).where(
        Invite.token_hmac == token_hmac(token), Workspace.deleted_at.is_(None)))).first()
    if row is None or row[0].revoked_at is not None or row[0].accepted_at is not None:
        raise not_found("Invite")
    return row[0], row[1]


@router.get("/invites/{token}", response_model=InvitePublicOut)
async def view_invite(token: str, db: DB) -> InvitePublicOut:
    inv, ws = await _invite_by_token(db, token)
    return InvitePublicOut(workspace_name=ws.name, workspace_slug=ws.slug, email=inv.email, role=inv.role,
                           expired=inv.expires_at <= datetime.now(UTC))


@router.post("/invites/{token}/accept", response_model=WorkspaceOut)
async def accept_invite(token: str, db: DB, principal: UserPrincipal) -> WorkspaceOut:
    inv, ws = await _invite_by_token(db, token)
    user = principal.user
    assert user is not None
    if inv.expires_at <= datetime.now(UTC):
        raise Problem(410, "Gone", "This invite has expired. Ask for a new one.", code="invite_expired")
    if not user.email_verified or user.email.lower() != inv.email.lower():
        raise Problem(403, "Forbidden", f"This invite is for {inv.email}. Sign in with that (verified) email.",
                      code="invite_email_mismatch")
    existing = (await db.execute(select(Membership).where(Membership.workspace_id == ws.id,
                                                          Membership.user_id == user.id))).scalar_one_or_none()
    if existing is None:
        db.add(Membership(workspace_id=ws.id, user_id=user.id, role=inv.role))
    inv.accepted_at = datetime.now(UTC)
    audit(db, "invite.accepted", actor=user.id, workspace_id=ws.id)
    await db.flush()
    return await _out(db, ws, existing.role if existing else inv.role)
