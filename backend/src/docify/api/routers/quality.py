"""Insights, policy checks + findings, and issues with responsible-contributor analysis (D66)."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from docify import checks, insights
from docify import issues as triage
from docify.api.deps import DB, CurrentPrincipal, UserPrincipal, get_workspace, load_for_user
from docify.api.errors import Problem, conflict, not_found
from docify.api.schemas import (
    ContributorOut,
    FindingOut,
    FindingPatch,
    FindingsOut,
    GithubImportIn,
    GithubIssueOut,
    IssueIn,
    IssueOut,
    IssuePatch,
    Ok,
    PolicyIn,
    PolicyOut,
    PolicyPatch,
    PolicyTemplateOut,
    PolicyTestIn,
    PolicyTestOut,
    ScanIn,
    ScanOut,
)
from docify.audit import audit
from docify.cache import hit
from docify.db.models import Finding, Issue, Policy, Repository, Workspace

router = APIRouter(tags=["insights, checks & issues"])
ACTIVE = ("ready", "indexing")


async def _repos(db: DB, ws: Workspace, repo_id: uuid.UUID | None = None) -> list[Repository]:
    q = select(Repository).where(Repository.workspace_id == ws.id, Repository.status.in_(ACTIVE))
    if repo_id:
        q = q.where(Repository.id == repo_id)
    return list((await db.execute(q.order_by(Repository.full_name))).scalars())


# ----------------------------------------------------------------------------- insights


@router.get("/repos/{repo_id}/insights", summary="Contributors, activity, languages, PRs, health")
async def repo_insights(repo_id: uuid.UUID, db: DB, principal: CurrentPrincipal,
                        refresh: bool = False) -> dict[str, Any]:
    repo, _ = await load_for_user(db, Repository, repo_id, principal)
    if repo.status == "disconnected":
        raise not_found("Repository")
    if refresh and principal.is_anonymous:
        refresh = False
    if refresh:
        await hit(f"insights-refresh:{repo.id}", limit=20, window_s=3600)
    await insights.refresh_github_stats(db, repo, force=refresh)
    return await insights.repo_insights(db, repo)


@router.get("/workspaces/{ws}/contributors", response_model=list[ContributorOut])
async def contributors(ws: str, db: DB, principal: CurrentPrincipal) -> list[ContributorOut]:
    w = await get_workspace(db, principal, ws)
    return [ContributorOut(login=c["login"], name=c["name"] or c["login"] or "unknown", commits=c["commits"],
                           last_commit=c["last_commit"]) for c in await insights.workspace_contributors(db, w.id)]


# ----------------------------------------------------------------------------- policies


@router.get("/policy-templates", response_model=list[PolicyTemplateOut])
async def policy_templates() -> list[PolicyTemplateOut]:
    return [PolicyTemplateOut(key=k, name=t["name"], description=t["description"], kind=t["kind"],
                              severity=t["severity"], paths=t["paths"], enabled=t["enabled"])
            for k, t in checks.TEMPLATES.items()]


@router.get("/workspaces/{ws}/policies", response_model=list[PolicyOut])
async def list_policies(ws: str, db: DB, principal: CurrentPrincipal) -> list[PolicyOut]:
    w = await get_workspace(db, principal, ws)
    if principal.role_in(w.id) is not None:
        await checks.ensure_default_policies(db, w.id)
    rows = (await db.execute(select(Policy).where(Policy.workspace_id == w.id)
                             .order_by(Policy.created_at, Policy.name))).scalars()
    return [PolicyOut.model_validate(p) for p in rows]


def _validate(kind: str, pattern: str) -> None:
    try:
        checks.compile_pattern(kind, pattern)
    except checks.PolicyError as exc:
        raise Problem(422, "Invalid pattern", str(exc), code="invalid_pattern") from exc


@router.post("/workspaces/{ws}/policies", response_model=PolicyOut, status_code=201)
async def create_policy(ws: str, body: PolicyIn, db: DB, principal: UserPrincipal) -> PolicyOut:
    w = await get_workspace(db, principal, ws, "admin")
    _validate(body.kind, body.pattern)
    if (await db.execute(select(Policy.id).where(Policy.workspace_id == w.id, Policy.name == body.name))).first():
        raise conflict("A policy with this name already exists.", code="policy_exists")
    p = Policy(workspace_id=w.id, name=body.name, description=body.description, kind=body.kind,
               pattern=body.pattern.strip(), severity=body.severity, paths=(body.paths or "").strip() or None,
               enabled=body.enabled, created_by=principal.user_id)
    db.add(p)
    await db.flush()
    audit(db, "policy.create", actor=principal.user_id, workspace_id=w.id, target=str(p.id), name=p.name)
    return PolicyOut.model_validate(p)


@router.patch("/policies/{policy_id}", response_model=PolicyOut)
async def update_policy(policy_id: uuid.UUID, body: PolicyPatch, db: DB, principal: UserPrincipal) -> PolicyOut:
    p, w = await load_for_user(db, Policy, policy_id, principal, "admin")
    data = body.model_dump(exclude_unset=True)
    kind, pattern = data.get("kind", p.kind), data.get("pattern", p.pattern)
    if "kind" in data or "pattern" in data:
        _validate(kind, pattern)
    for k, v in data.items():
        setattr(p, k, (v.strip() or None) if k == "paths" and isinstance(v, str) else v)
    audit(db, "policy.update", actor=principal.user_id, workspace_id=w.id, target=str(p.id), fields=sorted(data))
    return PolicyOut.model_validate(p)


@router.delete("/policies/{policy_id}", response_model=Ok)
async def delete_policy(policy_id: uuid.UUID, db: DB, principal: UserPrincipal) -> Ok:
    p, w = await load_for_user(db, Policy, policy_id, principal, "admin")
    await db.delete(p)
    audit(db, "policy.delete", actor=principal.user_id, workspace_id=w.id, target=str(policy_id))
    return Ok(message="Policy deleted. Its existing findings are kept.")


@router.post("/policies/test", response_model=PolicyTestOut, summary="Try a pattern against sample text")
async def test_policy(body: PolicyTestIn, principal: UserPrincipal) -> PolicyTestOut:
    try:
        rx = checks.compile_pattern(body.kind, body.pattern)
    except checks.PolicyError as exc:
        return PolicyTestOut(ok=False, error=str(exc))
    out = []
    for i, line in enumerate(body.sample.splitlines()[:200], 1):
        m = rx.search(line[: checks.MAX_LINE])
        if m and m.group(0).strip():
            out.append({"line": i, "text": line[:200], "match": m.group(0)[:100]})
    return PolicyTestOut(ok=True, matches=out[:50])


@router.post("/workspaces/{ws}/checks/scan", response_model=ScanOut, summary="Scan current code now")
async def scan_now(ws: str, body: ScanIn, db: DB, principal: UserPrincipal) -> ScanOut:
    w = await get_workspace(db, principal, ws, "admin")
    await hit(f"scan:{w.id}", limit=20, window_s=3600)
    repos = await _repos(db, w, body.repo_id)
    from docify.config import get_settings
    from docify.github.client import GitHubApp

    app = GitHubApp() if get_settings().github_configured else None
    created = 0
    try:
        for r in repos:
            gh = None
            if app is not None:
                try:
                    gh = await app.for_installation(r.installation_id)
                except Exception:
                    gh = None
            created += await checks.scan_repo(db, r, gh)
    finally:
        if app is not None:
            await app.aclose()
    audit(db, "checks.scan", actor=principal.user_id, workspace_id=w.id, repos=len(repos), created=created)
    return ScanOut(repos=len(repos), findings_created=created)


# ----------------------------------------------------------------------------- findings


def _finding_out(f: Finding, full_name: str, issue_no: int | None = None) -> FindingOut:
    out = FindingOut.model_validate(f, from_attributes=True).model_copy(
        update={"repo_full_name": full_name, "issue_number": issue_no})
    if f.commit_sha:
        anchor = f"#L{f.line}" if f.line else ""
        out.url = f"https://github.com/{full_name}/blob/{f.commit_sha}/{f.path}{anchor}"
    return out


@router.get("/workspaces/{ws}/findings", response_model=FindingsOut)
async def list_findings(ws: str, db: DB, principal: CurrentPrincipal, status: str | None = None,
                        severity: str | None = None, repo: uuid.UUID | None = None, author: str | None = None,
                        limit: int = Query(200, ge=1, le=500)) -> FindingsOut:
    w = await get_workspace(db, principal, ws)
    q = (select(Finding, Repository.full_name, Issue.number)
         .join(Repository, Repository.id == Finding.repo_id)
         .outerjoin(Issue, Issue.finding_id == Finding.id)
         .where(Finding.workspace_id == w.id))
    if status:
        q = q.where(Finding.status == status)
    if severity:
        q = q.where(Finding.severity == severity)
    if repo:
        q = q.where(Finding.repo_id == repo)
    if author:
        q = q.where((Finding.author_login == author) | (Finding.author_name == author))
    rank = func.array_position(["critical", "high", "medium", "low", "info"], Finding.severity)
    rows = (await db.execute(q.order_by(rank, Finding.created_at.desc()).limit(limit))).all()
    counts = dict((await db.execute(select(Finding.status, func.count()).where(Finding.workspace_id == w.id)
                                    .group_by(Finding.status))).all())
    return FindingsOut(items=[_finding_out(f, n, i) for f, n, i in rows], counts=counts)


@router.patch("/findings/{finding_id}", response_model=FindingOut)
async def update_finding(finding_id: uuid.UUID, body: FindingPatch, db: DB, principal: UserPrincipal) -> FindingOut:
    f, w = await load_for_user(db, Finding, finding_id, principal, "member")
    data = body.model_dump(exclude_unset=True)
    if "status" in data:
        f.status = data["status"]
        f.resolved_by = principal.user_id if f.status in ("resolved", "false_positive") else None
        f.resolved_at = checks.now() if f.status in ("resolved", "false_positive") else None
    if "assignee_login" in data:
        f.assignee_login = (data["assignee_login"] or "").strip() or None
    if "note" in data:
        f.note = data["note"]
    audit(db, "finding.update", actor=principal.user_id, workspace_id=w.id, target=str(f.id), fields=sorted(data))
    repo = await db.get(Repository, f.repo_id)
    return _finding_out(f, repo.full_name if repo else "")


@router.post("/findings/{finding_id}/issue", response_model=IssueOut, status_code=201,
             summary="Open an issue for a finding (suspect = the author who added the line)")
async def finding_to_issue(finding_id: uuid.UUID, db: DB, principal: UserPrincipal) -> IssueOut:
    f, w = await load_for_user(db, Finding, finding_id, principal, "member")
    existing = (await db.execute(select(Issue).where(Issue.finding_id == f.id))).scalar_one_or_none()
    if existing is not None:
        return await _issue_out(db, existing)
    body = (f"Policy **{f.policy_name}** ({f.severity}) flagged `{f.path}`"
            + (f" line {f.line}" if f.line else "") + f":\n\n```\n{f.snippet}\n```\n"
            + (f"\nIntroduced in {f.commit_sha[:7]} by {f.author_login or f.author_name}." if f.commit_sha else ""))
    issue = Issue(workspace_id=w.id, repo_id=f.repo_id, number=await triage.next_number(db, w.id),
                  title=f"{f.policy_name}: {f.path}"[:300], body=body, severity=f.severity, source="finding",
                  paths=[f.path], finding_id=f.id, created_by=principal.user_id)
    db.add(issue)
    await db.flush()
    await _analyze(db, w, issue)
    if f.status == "open":
        f.status = "acknowledged"
    audit(db, "issue.create", actor=principal.user_id, workspace_id=w.id, target=str(issue.id), source="finding")
    return await _issue_out(db, issue)


# ----------------------------------------------------------------------------- issues


async def _issue_out(db: DB, i: Issue) -> IssueOut:
    full = (await db.execute(select(Repository.full_name).where(Repository.id == i.repo_id))).scalar_one_or_none() \
        if i.repo_id else None
    return IssueOut.model_validate(i, from_attributes=True).model_copy(update={"repo_full_name": full})


async def _analyze(db: DB, w: Workspace, issue: Issue) -> None:
    repos = await _repos(db, w)
    issue.suspects = await triage.analyze(db, issue, repos)
    issue.analyzed_at = triage.now()


@router.get("/workspaces/{ws}/issues", response_model=list[IssueOut])
async def list_issues(ws: str, db: DB, principal: CurrentPrincipal, status: str | None = None,
                      assignee: str | None = None) -> list[IssueOut]:
    w = await get_workspace(db, principal, ws)
    q = select(Issue).where(Issue.workspace_id == w.id)
    if status:
        q = q.where(Issue.status.in_(status.split(",")))
    if assignee:
        q = q.where(Issue.assignee_login == assignee)
    rows = (await db.execute(q.order_by(Issue.number.desc()).limit(300))).scalars().all()
    names = dict((await db.execute(select(Repository.id, Repository.full_name)
                                   .where(Repository.workspace_id == w.id))).all())
    return [IssueOut.model_validate(i, from_attributes=True).model_copy(
        update={"repo_full_name": names.get(i.repo_id) if i.repo_id else None}) for i in rows]


@router.post("/workspaces/{ws}/issues", response_model=IssueOut, status_code=201)
async def create_issue(ws: str, body: IssueIn, db: DB, principal: UserPrincipal) -> IssueOut:
    w = await get_workspace(db, principal, ws, "member")
    await hit(f"issue-create:{principal.user_id}", limit=60, window_s=3600)
    if body.repo_id and not await _repos(db, w, body.repo_id):
        raise not_found("Repository")
    issue = Issue(workspace_id=w.id, repo_id=body.repo_id, number=await triage.next_number(db, w.id),
                  title=body.title.strip(), body=body.body, severity=body.severity, source="docify",
                  paths=[p.strip() for p in body.paths if p.strip()][:20], created_by=principal.user_id)
    db.add(issue)
    await db.flush()
    await _analyze(db, w, issue)
    audit(db, "issue.create", actor=principal.user_id, workspace_id=w.id, target=str(issue.id), source="docify")
    return await _issue_out(db, issue)


@router.get("/issues/{issue_id}", response_model=IssueOut)
async def get_issue(issue_id: uuid.UUID, db: DB, principal: CurrentPrincipal) -> IssueOut:
    i, _ = await load_for_user(db, Issue, issue_id, principal)
    return await _issue_out(db, i)


@router.patch("/issues/{issue_id}", response_model=IssueOut)
async def update_issue(issue_id: uuid.UUID, body: IssuePatch, db: DB, principal: UserPrincipal) -> IssueOut:
    i, w = await load_for_user(db, Issue, issue_id, principal, "member")
    data = body.model_dump(exclude_unset=True)
    for k in ("title", "body", "severity"):
        if k in data and data[k] is not None:
            setattr(i, k, data[k])
    if data.get("status"):
        i.status = data["status"]
        i.closed_at = triage.now() if i.status in ("resolved", "closed") else None
    if data.get("unassign"):
        i.assignee_login, i.assigned_at, i.assigned_by = None, None, None
    elif data.get("assignee_login"):
        i.assignee_login = data["assignee_login"].strip()
        i.assigned_at, i.assigned_by = triage.now(), principal.user_id
        if i.status == "open":
            i.status = "in_progress"
    audit(db, "issue.update", actor=principal.user_id, workspace_id=w.id, target=str(i.id), fields=sorted(data))
    return await _issue_out(db, i)


@router.post("/issues/{issue_id}/analyze", response_model=IssueOut, summary="Re-run responsible-contributor analysis")
async def reanalyze(issue_id: uuid.UUID, db: DB, principal: UserPrincipal) -> IssueOut:
    i, w = await load_for_user(db, Issue, issue_id, principal, "member")
    await hit(f"issue-analyze:{principal.user_id}", limit=60, window_s=3600)
    await _analyze(db, w, i)
    return await _issue_out(db, i)


@router.delete("/issues/{issue_id}", response_model=Ok)
async def delete_issue(issue_id: uuid.UUID, db: DB, principal: UserPrincipal) -> Ok:
    i, w = await load_for_user(db, Issue, issue_id, principal, "admin")
    await db.delete(i)
    audit(db, "issue.delete", actor=principal.user_id, workspace_id=w.id, target=str(issue_id))
    return Ok()


# ----------------------------------------------------------------------------- GitHub issues


@router.get("/workspaces/{ws}/github-issues", response_model=list[GithubIssueOut])
async def github_issues(ws: str, db: DB, principal: UserPrincipal, repo_id: uuid.UUID,
                        state: str = Query("open", pattern="^(open|closed|all)$")) -> list[GithubIssueOut]:
    w = await get_workspace(db, principal, ws, "member")
    repos = await _repos(db, w, repo_id)
    if not repos:
        raise not_found("Repository")
    await hit(f"gh-issues:{w.id}", limit=120, window_s=3600)
    from docify.github.client import GitHubApp, GitHubNotFound

    app = GitHubApp()
    try:
        gh = await app.for_installation(repos[0].installation_id)
        items = await gh.list_issues(repos[0].full_name, state=state)
    except GitHubNotFound as exc:
        raise Problem(403, "Forbidden", "GitHub didn't share this repository's issues with Docify (the app needs "
                      "the Issues permission for private repositories).", code="issues_unavailable") from exc
    finally:
        await app.aclose()
    imported = dict((await db.execute(select(Issue.github_number, Issue.number).where(
        Issue.workspace_id == w.id, Issue.repo_id == repo_id, Issue.github_number.is_not(None)))).all())
    return [GithubIssueOut(number=i["number"], title=i.get("title", "")[:300], state=i.get("state", ""),
                           author=(i.get("user") or {}).get("login"),
                           labels=[lb.get("name", "") for lb in i.get("labels") or [] if isinstance(lb, dict)],
                           comments=i.get("comments", 0), url=i.get("html_url", ""), created_at=i["created_at"],
                           imported_issue_number=imported.get(i["number"])) for i in items]


@router.post("/workspaces/{ws}/github-issues/import", response_model=IssueOut, status_code=201)
async def import_github_issue(ws: str, body: GithubImportIn, db: DB, principal: UserPrincipal) -> IssueOut:
    w = await get_workspace(db, principal, ws, "member")
    repos = await _repos(db, w, body.repo_id)
    if not repos:
        raise not_found("Repository")
    existing = (await db.execute(select(Issue).where(Issue.workspace_id == w.id, Issue.repo_id == body.repo_id,
                                                     Issue.github_number == body.number))).scalar_one_or_none()
    if existing is not None:
        return await _issue_out(db, existing)
    from docify.github.client import GitHubApp, GitHubNotFound

    app = GitHubApp()
    try:
        gh = await app.for_installation(repos[0].installation_id)
        found = next((i for i in await gh.list_issues(repos[0].full_name, state="all") if i["number"] == body.number),
                     None)
    except GitHubNotFound as exc:
        raise Problem(403, "Forbidden", "GitHub didn't share this repository's issues with Docify.",
                      code="issues_unavailable") from exc
    finally:
        await app.aclose()
    if found is None:
        raise not_found("GitHub issue")
    issue = Issue(workspace_id=w.id, repo_id=body.repo_id, number=await triage.next_number(db, w.id),
                  title=found.get("title", "")[:300], body=(found.get("body") or "")[:20000], source="github",
                  github_number=body.number, github_url=found.get("html_url"),
                  github_author=(found.get("user") or {}).get("login"),
                  status="closed" if found.get("state") == "closed" else "open", created_by=principal.user_id)
    db.add(issue)
    await db.flush()
    await _analyze(db, w, issue)
    audit(db, "issue.import", actor=principal.user_id, workspace_id=w.id, target=str(issue.id), number=body.number)
    return await _issue_out(db, issue)
