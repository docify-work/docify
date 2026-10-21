"""Repos, docs, changelog, review queue, jobs."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Query
from sqlalchemy import exists, select, update
from sqlalchemy.orm import aliased

from docify.ai.citations import render
from docify.api import pagination
from docify.api.deps import DB, CurrentPrincipal, UserPrincipal, get_workspace, load_for_user
from docify.api.errors import Problem, conflict, not_found
from docify.api.routers.github import repo_out
from docify.api.schemas import (
    ChangelogOut,
    DocDetailOut,
    DocOut,
    DocVersionOut,
    JobOut,
    Ok,
    Page,
    RepoOut,
    ReviewItemOut,
    VersionBrief,
)
from docify.audit import audit
from docify.cache import hit
from docify.db.models import ChangelogEntry, Document, DocumentVersion, Job, Repository
from docify.jobs import service as jobs

router = APIRouter(tags=["repos"])


# ----------------------------------------------------------------------------- repos


@router.get("/workspaces/{ws}/repos", response_model=list[RepoOut])
async def list_repos(ws: str, db: DB, principal: CurrentPrincipal) -> list[RepoOut]:
    w = await get_workspace(db, principal, ws)
    rows = (await db.execute(select(Repository).where(Repository.workspace_id == w.id,
                                                      Repository.status != "disconnected")
                             .order_by(Repository.full_name))).scalars()
    return [repo_out(r) for r in rows]


@router.get("/repos/{repo_id}", response_model=RepoOut)
async def get_repo(repo_id: uuid.UUID, db: DB, principal: CurrentPrincipal) -> RepoOut:
    repo, _ = await load_for_user(db, Repository, repo_id, principal)
    if repo.status == "disconnected":
        raise not_found("Repository")
    return repo_out(repo)


async def _queue_repo_job(db: DB, principal: UserPrincipal, repo_id: uuid.UUID, job_type: str) -> Ok:
    repo, ws = await load_for_user(db, Repository, repo_id, principal, "admin")
    if repo.status in ("disconnected", "suspended"):
        raise conflict("This repository can't be synced right now.", code="repo_inactive")
    await hit(f"resync:{repo.id}", limit=10, window_s=3600)
    job = await jobs.enqueue(db, job_type, workspace_id=ws.id, repo_id=repo.id, payload={"reason": "manual"})
    audit(db, f"repo.{job_type}", actor=principal.user_id, workspace_id=ws.id, target=repo.full_name)
    await db.commit()
    await jobs.dispatch([job.job_id])
    return Ok(message="Queued.")


@router.post("/repos/{repo_id}/resync", response_model=Ok, status_code=202)
async def resync(repo_id: uuid.UUID, db: DB, principal: UserPrincipal) -> Ok:
    return await _queue_repo_job(db, principal, repo_id, "repo_sync")


@router.post("/repos/{repo_id}/reindex", response_model=Ok, status_code=202)
async def reindex(repo_id: uuid.UUID, db: DB, principal: UserPrincipal) -> Ok:
    return await _queue_repo_job(db, principal, repo_id, "repo_index")


@router.delete("/repos/{repo_id}", response_model=Ok, status_code=202)
async def remove_repo(repo_id: uuid.UUID, db: DB, principal: UserPrincipal) -> Ok:
    repo, ws = await load_for_user(db, Repository, repo_id, principal, "admin")
    repo.status = "disconnected"
    job = await jobs.enqueue(db, "repo_purge", workspace_id=ws.id, repo_id=repo.id, payload={"reason": "removed"})
    audit(db, "repo.removed", actor=principal.user_id, workspace_id=ws.id, target=repo.full_name)
    await db.commit()
    await jobs.dispatch([job.job_id])
    return Ok(message="Repository removed. Its data will be deleted shortly.")


# ----------------------------------------------------------------------------- docs


def _brief(v: DocumentVersion | None) -> VersionBrief | None:
    return VersionBrief.model_validate(v) if v is not None else None


@router.get("/workspaces/{ws}/docs", response_model=list[DocOut])
async def list_docs(ws: str, db: DB, principal: CurrentPrincipal, repo: uuid.UUID | None = None) -> list[DocOut]:
    w = await get_workspace(db, principal, ws)
    pv = aliased(DocumentVersion)
    pending = (select(pv.id).where(pv.document_id == Document.id, pv.status == "pending_review")
               .correlate(Document).exists())
    q = (select(Document, Repository.full_name, DocumentVersion, pending.label("pending"))
         .join(Repository, Repository.id == Document.repo_id)
         .outerjoin(DocumentVersion, DocumentVersion.id == Document.published_version_id)
         .where(Document.workspace_id == w.id, Repository.status != "disconnected"))
    if repo is not None:
        q = q.where(Document.repo_id == repo)
    order = {"overview": 0, "setup": 1, "api": 2}
    rows = list((await db.execute(q)).all())
    rows.sort(key=lambda r: (r[1], order.get(r[0].kind, 9)))
    return [DocOut(id=d.id, repo_id=d.repo_id, repo_full_name=name, kind=d.kind, title=d.title, published=_brief(v),
                   has_pending_review=bool(p), updated_at=v.created_at if v else d.created_at)
            for d, name, v, p in rows]


@router.get("/docs/{doc_id}", response_model=DocDetailOut)
async def get_doc(doc_id: uuid.UUID, db: DB, principal: CurrentPrincipal) -> DocDetailOut:
    doc, _ = await load_for_user(db, Document, doc_id, principal)
    repo = await db.get(Repository, doc.repo_id)
    if repo is None or repo.status == "disconnected":
        raise not_found("Document")
    v = await db.get(DocumentVersion, doc.published_version_id) if doc.published_version_id else None
    pending = (await db.execute(select(exists().where(DocumentVersion.document_id == doc.id,
                                                      DocumentVersion.status == "pending_review")))).scalar()
    return DocDetailOut(id=doc.id, repo_id=doc.repo_id, repo_full_name=repo.full_name, kind=doc.kind, title=doc.title,
                        published=_brief(v), has_pending_review=bool(pending),
                        updated_at=v.created_at if v else doc.created_at,
                        content_md=render(v.content_md, repo.full_name, v.commit_sha) if v else None,
                        source_paths=list(doc.source_paths or []),
                        repo_html_url=f"https://github.com/{repo.full_name}",
                        commit_url=f"https://github.com/{repo.full_name}/commit/{v.commit_sha}" if v else None)


@router.get("/docs/{doc_id}/versions", response_model=list[DocVersionOut])
async def doc_versions(doc_id: uuid.UUID, db: DB, principal: CurrentPrincipal) -> list[DocVersionOut]:
    doc, _ = await load_for_user(db, Document, doc_id, principal)
    repo = await db.get(Repository, doc.repo_id)
    assert repo is not None
    statuses = ["published", "superseded"] if principal.role_in(doc.workspace_id) is None else \
        ["published", "superseded", "pending_review", "rejected"]
    rows = (await db.execute(select(DocumentVersion).where(DocumentVersion.document_id == doc.id,
                                                           DocumentVersion.status.in_(statuses))
                             .order_by(DocumentVersion.version.desc()).limit(50))).scalars()
    return [DocVersionOut(id=v.id, version=v.version, status=v.status, commit_sha=v.commit_sha, model=v.model,
                          partial=v.partial, created_at=v.created_at,
                          content_md=render(v.content_md, repo.full_name, v.commit_sha)) for v in rows]


@router.get("/repos/{repo_id}/changelog", response_model=Page[ChangelogOut])
async def changelog(repo_id: uuid.UUID, db: DB, principal: CurrentPrincipal, cursor: str | None = None,
                    limit: int = Query(default=20, ge=1, le=100)) -> Page[ChangelogOut]:
    repo, _ = await load_for_user(db, Repository, repo_id, principal)
    q = select(ChangelogEntry).where(ChangelogEntry.repo_id == repo.id, ChangelogEntry.status == "published")
    rows = list((await db.execute(pagination.apply(q, ChangelogEntry, cursor, limit))).scalars())
    rows, nxt = pagination.next_cursor(rows, limit)
    return Page[ChangelogOut](items=[ChangelogOut.model_validate(r) for r in rows], next_cursor=nxt)


# ----------------------------------------------------------------------------- review queue


@router.get("/workspaces/{ws}/review", response_model=list[ReviewItemOut])
async def review_queue(ws: str, db: DB, principal: UserPrincipal) -> list[ReviewItemOut]:
    w = await get_workspace(db, principal, ws, "admin")
    out: list[ReviewItemOut] = []
    versions = (await db.execute(
        select(DocumentVersion, Document, Repository.full_name)
        .join(Document, Document.id == DocumentVersion.document_id)
        .join(Repository, Repository.id == Document.repo_id)
        .where(DocumentVersion.workspace_id == w.id, DocumentVersion.status == "pending_review")
        .order_by(DocumentVersion.created_at))).all()
    for v, d, name in versions:
        base = await db.get(DocumentVersion, d.published_version_id) if d.published_version_id else None
        out.append(ReviewItemOut(kind="doc", id=v.id, repo_id=d.repo_id, repo_full_name=name,
                                 title=f"{d.title} (v{v.version})", content_md=render(v.content_md, name, v.commit_sha),
                                 base_content_md=render(base.content_md, name, base.commit_sha) if base else None,
                                 created_at=v.created_at))
    entries = (await db.execute(
        select(ChangelogEntry, Repository.full_name).join(Repository, Repository.id == ChangelogEntry.repo_id)
        .where(ChangelogEntry.workspace_id == w.id, ChangelogEntry.status == "pending_review")
        .order_by(ChangelogEntry.created_at))).all()
    for e, name in entries:
        out.append(ReviewItemOut(kind="changelog", id=e.id, repo_id=e.repo_id, repo_full_name=name,
                                 title=f"Changelog {(e.from_sha or '')[:7]}…{e.to_sha[:7]}", content_md=e.content_md,
                                 base_content_md=None, created_at=e.created_at))
    return out


@router.post("/review/{kind}/{item_id}/{decision}", response_model=Ok)
async def review_decide(kind: str, item_id: uuid.UUID, decision: str, db: DB, principal: UserPrincipal) -> Ok:
    if kind not in ("doc", "changelog") or decision not in ("approve", "reject"):
        raise not_found("Review item")
    now = datetime.now(UTC)
    if kind == "changelog":
        entry, ws = await load_for_user(db, ChangelogEntry, item_id, principal, "admin")
        if entry.status != "pending_review":
            raise conflict("Already reviewed.", code="already_reviewed")
        entry.status = "published" if decision == "approve" else "rejected"
        entry.reviewed_by, entry.reviewed_at = principal.user_id, now
        audit(db, f"review.changelog_{decision}", actor=principal.user_id, workspace_id=ws.id, target=str(item_id))
        return Ok()
    ver, ws = await load_for_user(db, DocumentVersion, item_id, principal, "admin")
    if ver.status != "pending_review":
        raise conflict("Already reviewed.", code="already_reviewed")
    doc = await db.get(Document, ver.document_id)
    assert doc is not None
    if decision == "approve":
        # Compare-and-set: approve only if nobody published something else meanwhile (§11.3 item 7).
        res = await db.execute(update(Document).where(Document.id == doc.id,
                                                      Document.published_version_id.is_not_distinct_from(
                                                          doc.published_version_id))
                               .values(published_version_id=ver.id, title=_title(ver.content_md, doc.title)))
        if res.rowcount != 1:  # type: ignore[attr-defined]
            raise Problem(409, "Conflict", "The document changed meanwhile. Reload and review again.",
                          code="review_conflict")
        ver.status = "published"
    else:
        ver.status = "rejected"
    ver.reviewed_by, ver.reviewed_at = principal.user_id, now
    audit(db, f"review.doc_{decision}", actor=principal.user_id, workspace_id=ws.id, target=str(item_id))
    return Ok()


def _title(md: str, fallback: str) -> str:
    first = md.lstrip().split("\n", 1)[0]
    return first.lstrip("# ").strip()[:200] if first.startswith("#") else fallback


# ----------------------------------------------------------------------------- jobs


@router.get("/workspaces/{ws}/jobs", response_model=Page[JobOut])
async def list_jobs(ws: str, db: DB, principal: UserPrincipal, cursor: str | None = None,
                    limit: int = Query(default=30, ge=1, le=100), status: str | None = None) -> Page[JobOut]:
    w = await get_workspace(db, principal, ws, "member")
    q = select(Job, Repository.full_name).outerjoin(Repository, Repository.id == Job.repo_id).where(
        Job.workspace_id == w.id)
    if status:
        q = q.where(Job.status == status)
    rows: list[Any] = list((await db.execute(pagination.apply(q, Job, cursor, limit))).all())  # type: ignore[arg-type]
    rows, nxt = pagination.next_cursor(rows, limit, get=lambda r: r[0])
    items = [JobOut(id=j.id, type=j.type, status=j.status, attempts=j.attempts, max_attempts=j.max_attempts,
                    repo_id=j.repo_id, repo_full_name=name, error=j.error, created_at=j.created_at,
                    started_at=j.started_at, finished_at=j.finished_at, run_after=j.run_after) for j, name in rows]
    return Page[JobOut](items=items, next_cursor=nxt)


@router.post("/jobs/{job_id}/retry", response_model=Ok, status_code=202)
async def retry(job_id: uuid.UUID, db: DB, principal: UserPrincipal) -> Ok:
    job, ws = await load_for_user(db, Job, job_id, principal, "admin")
    if job.status not in ("failed", "dead"):
        raise conflict("Only failed or dead jobs can be retried.", code="not_retryable")
    if job.repo_id:
        repo = await db.get(Repository, job.repo_id)
        if repo is not None and repo.status in ("error", "too_large", "empty"):
            repo.status = "pending" if not repo.last_processed_sha else "ready"
    open_id = await jobs.retry_job(db, job)
    audit(db, "job.retried", actor=principal.user_id, workspace_id=ws.id, target=str(job_id))
    await db.commit()
    if open_id:
        await jobs.dispatch([open_id])
    return Ok(message="Retry queued.")
