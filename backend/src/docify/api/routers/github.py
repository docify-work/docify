"""GitHub App install + attach flow (Master Doc §9.2).

1. Admin → install URL (state bound to session + workspace).
2. GitHub → Setup URL with installation_id → we send the user through OAuth.
3. OAuth callback: the installation must appear in the *user's* `/user/installations`
   (prevents someone from claiming another person's installation id — F52).
4. Ownership is never changed by upserts; repos are attached explicitly by an admin.
"""

from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select

from docify.api.deps import DB, CurrentPrincipal, Principal, UserPrincipal, get_workspace
from docify.api.errors import Problem, conflict
from docify.api.routers.auth import _front, new_oauth_state
from docify.api.schemas import AttachReposIn, GithubRepoOption, InstallationOut, InstallUrlOut, RepoOut
from docify.audit import audit
from docify.auth import oauth
from docify.auth.tokens import token_hmac
from docify.config import get_settings
from docify.db.models import GithubInstallation, OAuthState, Repository, Workspace, WorkspaceInstallation
from docify.github.client import GitHubApp, GitHubNotFound
from docify.jobs import service as jobs
from docify.jobs.errors import JobError

router = APIRouter(tags=["github"])


def repo_out(r: Repository) -> RepoOut:
    return RepoOut(id=r.id, workspace_id=r.workspace_id, full_name=r.full_name, owner=r.owner, name=r.name,
                   default_branch=r.default_branch, private=r.private, archived=r.archived, status=r.status,
                   last_processed_sha=r.last_processed_sha, last_synced_at=r.last_synced_at, error=r.error,
                   html_url=f"https://github.com/{r.full_name}", created_at=r.created_at)


def _require_github() -> None:
    if not get_settings().github_configured:
        raise Problem(503, "Unavailable", "GitHub integration is not configured on this server.",
                      code="github_not_configured")


@router.get("/workspaces/{ws}/github/install-url", response_model=InstallUrlOut)
async def install_url(ws: str, db: DB, principal: UserPrincipal) -> InstallUrlOut:
    _require_github()
    w = await get_workspace(db, principal, ws, "admin")
    state, _, _ = await new_oauth_state(db, provider="github", purpose="install", session=principal.session,
                                        workspace_id=w.id, redirect_to=f"/w/{w.slug}/repos")
    s = get_settings()
    return InstallUrlOut(url=f"{s.github_web_url}/apps/{s.github_app_slug}/installations/new?"
                             + urlencode({"state": state}))


@router.get("/github/setup", summary="GitHub App Setup URL (browser redirect)")
async def setup(request: Request, db: DB, principal: CurrentPrincipal, installation_id: int | None = None,
                setup_action: str | None = None, state: str | None = None) -> RedirectResponse:
    if principal.session is None:
        return RedirectResponse(_front("/login?error=login_required"), status_code=302)
    row: OAuthState | None = None
    now = datetime.now(UTC)
    if state:
        row = (await db.execute(select(OAuthState).where(OAuthState.state_hmac == token_hmac(state)))) \
            .scalar_one_or_none()
    if row is None:  # GitHub drops `state` on some paths (e.g. "configure" from GitHub UI)
        row = (await db.execute(select(OAuthState).where(
            OAuthState.session_id == principal.session.id, OAuthState.purpose == "install",
            OAuthState.expires_at > now).order_by(OAuthState.created_at.desc()).limit(1))).scalar_one_or_none()
    if row is None or row.session_id != principal.session.id or row.purpose != "install" or row.expires_at <= now \
            or installation_id is None:
        return RedirectResponse(_front("/?error=install_state"), status_code=302)
    await db.delete(row)
    # Fresh state for the OAuth leg, carrying the installation id to verify.
    new_state, challenge, _ = await new_oauth_state(db, provider="github", purpose="install",
                                                    session=principal.session, workspace_id=row.workspace_id,
                                                    redirect_to=row.redirect_to)
    created = (await db.execute(select(OAuthState).where(OAuthState.state_hmac == token_hmac(new_state)))).scalar_one()
    created.installation_id = installation_id
    return RedirectResponse(oauth.github_authorize_url(new_state, challenge), status_code=302)


async def complete_install(db: DB, principal: Principal, row: OAuthState, profile: oauth.ProviderProfile) -> str:
    """Called from the OAuth callback for purpose=install. Returns the SPA path to redirect to."""
    if principal.user is None or row.workspace_id is None or row.installation_id is None:
        return "/login?error=login_required"
    ws = await db.get(Workspace, row.workspace_id)
    if ws is None or ws.deleted_at is not None or principal.role_in(ws.id) != "admin":
        return "/?error=install_workspace"
    assert profile.access_token is not None
    try:
        allowed = await oauth.github_user_installation_ids(profile.access_token)
    except oauth.OAuthError:
        return f"/w/{ws.slug}/repos?error=install_verify"
    if row.installation_id not in allowed:
        audit(db, "github.install_rejected", actor=principal.user.id, workspace_id=ws.id,
              target=str(row.installation_id))
        return f"/w/{ws.slug}/repos?error=install_not_yours"
    app = GitHubApp()
    try:
        meta = await app.get_installation(row.installation_id)
    except (GitHubNotFound, JobError):
        return f"/w/{ws.slug}/repos?error=install_missing"
    finally:
        await app.aclose()
    account = meta.get("account") or {}
    inst = (await db.execute(select(GithubInstallation).where(
        GithubInstallation.installation_id == row.installation_id))).scalar_one_or_none()
    if inst is None:
        inst = GithubInstallation(installation_id=row.installation_id, account_login=account.get("login", "?"),
                                  account_type=account.get("type", "User"), installed_by_user_id=principal.user.id)
        db.add(inst)
    # Metadata only; never ownership.
    inst.account_login = account.get("login", inst.account_login)
    inst.account_type = account.get("type", inst.account_type)
    inst.repository_selection = meta.get("repository_selection")
    inst.permissions = meta.get("permissions") or {}
    inst.deleted_at = None
    await db.flush()
    exists = (await db.execute(select(WorkspaceInstallation).where(
        WorkspaceInstallation.workspace_id == ws.id,
        WorkspaceInstallation.installation_id == row.installation_id))).scalar_one_or_none()
    if exists is None:
        db.add(WorkspaceInstallation(workspace_id=ws.id, installation_id=row.installation_id,
                                     added_by=principal.user.id))
    audit(db, "github.installed", actor=principal.user.id, workspace_id=ws.id, target=str(row.installation_id))
    return f"/w/{ws.slug}/repos?connected=1"


@router.get("/workspaces/{ws}/github/installations", response_model=list[InstallationOut])
async def installations(ws: str, db: DB, principal: UserPrincipal) -> list[InstallationOut]:
    _require_github()
    w = await get_workspace(db, principal, ws, "admin")
    insts = (await db.execute(select(GithubInstallation).join(
        WorkspaceInstallation, WorkspaceInstallation.installation_id == GithubInstallation.installation_id)
        .where(WorkspaceInstallation.workspace_id == w.id, GithubInstallation.deleted_at.is_(None)))).scalars().all()
    out: list[InstallationOut] = []
    app = GitHubApp()
    try:
        for inst in insts:
            options: list[GithubRepoOption] = []
            if inst.suspended_at is None:
                try:
                    client = await app.for_installation(inst.installation_id)
                    repos = await client.list_repos()
                except (GitHubNotFound, JobError):
                    repos = []
                ids = [int(r["id"]) for r in repos]
                attached = {gid: (ws_id, slug) for gid, ws_id, slug in (await db.execute(
                    select(Repository.github_repo_id, Workspace.id, Workspace.slug)
                    .join(Workspace, Workspace.id == Repository.workspace_id)
                    .where(Repository.github_repo_id.in_(ids or [0])))).all()}
                for r in repos:
                    hit_ = attached.get(int(r["id"]))
                    # Don't leak other workspaces' names: show the slug only if you're a member there.
                    shown = None if hit_ is None else (hit_[1] if principal.role_in(hit_[0]) else "other")
                    options.append(GithubRepoOption(github_repo_id=int(r["id"]), full_name=r["full_name"],
                                                    private=bool(r.get("private")),
                                                    default_branch=r.get("default_branch"), attached_workspace=shown))
            out.append(InstallationOut(installation_id=inst.installation_id, account_login=inst.account_login,
                                       account_type=inst.account_type, suspended=inst.suspended_at is not None,
                                       repos=options))
    finally:
        await app.aclose()
    return out


@router.post("/workspaces/{ws}/github/installations/{installation_id}/repos", response_model=list[RepoOut],
             status_code=201)
async def attach_repos(ws: str, installation_id: int, body: AttachReposIn, db: DB,
                       principal: UserPrincipal) -> list[RepoOut]:
    _require_github()
    s = get_settings()
    w = await get_workspace(db, principal, ws, "admin")
    link = (await db.execute(select(WorkspaceInstallation).join(
        GithubInstallation, GithubInstallation.installation_id == WorkspaceInstallation.installation_id).where(
        WorkspaceInstallation.workspace_id == w.id, WorkspaceInstallation.installation_id == installation_id,
        GithubInstallation.deleted_at.is_(None)))).scalar_one_or_none()
    if link is None:
        raise Problem(404, "Not found", "Installation not connected to this workspace.", code="not_found")
    current = (await db.execute(select(func.count()).select_from(Repository).where(
        Repository.workspace_id == w.id, Repository.status != "disconnected"))).scalar_one()
    if current + len(body.github_repo_ids) > s.ws_max_repos:
        raise conflict(f"A workspace can have at most {s.ws_max_repos} repositories.", code="repo_limit")
    app = GitHubApp()
    try:
        client = await app.for_installation(installation_id)
        accessible = {int(r["id"]): r for r in await client.list_repos()}
    finally:
        await app.aclose()
    created: list[Repository] = []
    for gid in dict.fromkeys(body.github_repo_ids):
        meta = accessible.get(gid)
        if meta is None:
            raise Problem(404, "Not found", f"Repository {gid} is not accessible to this installation.",
                          code="repo_not_accessible")
        other = (await db.execute(select(Repository, Workspace.name).join(Workspace, Workspace.id ==
                                                                          Repository.workspace_id)
                                  .where(Repository.github_repo_id == gid))).first()
        if other is not None:
            if other[0].status == "disconnected":
                raise conflict("This repository is being removed. Try again in a minute.", code="repo_purging")
            raise conflict(f"Repo already used in workspace {other[1]}.", code="repo_in_use")
        repo = Repository(workspace_id=w.id, installation_id=installation_id, github_repo_id=gid,
                          owner=meta["owner"]["login"], name=meta["name"], full_name=meta["full_name"],
                          default_branch=meta.get("default_branch") or "main", private=bool(meta.get("private")),
                          archived=bool(meta.get("archived")), size_kb=meta.get("size"), status="pending")
        db.add(repo)
        await db.flush()
        await db.refresh(repo)
        created.append(repo)
        audit(db, "repo.attached", actor=principal.user_id, workspace_id=w.id, target=meta["full_name"])
    job_ids = [(await jobs.enqueue(db, "repo_index", workspace_id=w.id, repo_id=r.id,
                                   payload={"reason": "attach"})).job_id for r in created]
    await db.commit()
    await jobs.dispatch(job_ids)
    return [repo_out(r) for r in created]
