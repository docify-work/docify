"""Search (code/docs) and chat with citations over SSE (Master Doc §11.4–11.6)."""

from __future__ import annotations

import asyncio
import contextlib
import json
import uuid
from collections.abc import AsyncIterator
from typing import Any, Literal

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, text

from docify.ai.budget import check_budget, record_embedding, record_llm
from docify.ai.embeddings import get_embedder
from docify.ai.llm import LLMRefusal, Usage, get_llm
from docify.ai.prompts import CHAT_SYSTEM
from docify.ai.rag import build_sources_block, retrieve
from docify.api.deps import DB, CurrentPrincipal, Principal, UserPrincipal, get_workspace, load_for_user
from docify.api.errors import Problem, not_found
from docify.api.schemas import ChatIn, ChatMessageOut, Ok, SearchHitOut, SearchOut, ThreadDetailOut, ThreadOut
from docify.cache import daily_counter
from docify.config import get_settings
from docify.db.models import ChatMessage, ChatThread, Repository, Workspace
from docify.db.session import session_scope
from docify.jobs.errors import BudgetExceeded, JobError
from docify.observability.logging import get_logger
from docify.observability.metrics import CHAT_REQUESTS

router = APIRouter(tags=["search & chat"])
log = get_logger(__name__)
NO_CONTEXT = "I couldn't find this in the indexed code."
HISTORY_TURNS = 6
HISTORY_CHARS = 16_000
KEEPALIVE_S = 15


async def _repo_ids(db: DB, ws: Workspace, wanted: list[uuid.UUID] | None) -> list[uuid.UUID]:
    q = select(Repository.id).where(Repository.workspace_id == ws.id, Repository.status.in_(("ready", "indexing")))
    if wanted:
        q = q.where(Repository.id.in_(wanted))
    return list((await db.execute(q)).scalars())


async def _quota(principal: Principal, ws: Workspace, kind: Literal["chat", "search"]) -> None:
    s = get_settings()
    if kind == "search":
        if principal.is_anonymous:
            await daily_counter(f"search:anon:{principal.ip}", limit=s.search_anon_ip_daily_limit)
        return
    if principal.is_anonymous:
        await daily_counter(f"chat:anon:{principal.ip}", limit=s.chat_anon_ip_daily_limit)
        await daily_counter("chat:anon:global", limit=s.chat_anon_global_daily_limit)
    else:
        await daily_counter(f"chat:user:{principal.user_id}", limit=s.chat_user_daily_limit)


# ----------------------------------------------------------------------------- search


@router.get("/workspaces/{ws}/search", response_model=SearchOut)
async def search(ws: str, db: DB, principal: CurrentPrincipal, q: str = Query(min_length=2, max_length=300),
                 scope: Literal["code", "docs"] = "code", repo: uuid.UUID | None = None) -> SearchOut:
    w = await get_workspace(db, principal, ws)
    repo_ids = await _repo_ids(db, w, [repo] if repo else None)
    if scope == "docs":
        return SearchOut(query=q, scope=scope, hits=await _search_docs(db, w, repo_ids, q))
    await _quota(principal, w, "search")
    embedder = get_embedder()
    vec = None
    try:
        vectors, tokens = await embedder.embed([q], input_type="query")
        vec = vectors[0]
        record_embedding(db, workspace_id=w.id, job_id=None, model=embedder.model, tokens=tokens,
                         purpose="search_embed")
    except (JobError, Exception) as exc:  # F22: FTS-only fallback
        log.info("search.embed_failed", error=type(exc).__name__)
    hits, _ = await retrieve(db, workspace_id=w.id, repo_ids=repo_ids, query=q, embedder=embedder, query_vector=vec)
    return SearchOut(query=q, scope=scope, hits=[
        SearchHitOut(kind="code", repo_id=h.repo_id, repo_full_name=h.repo_full_name,
                     title=f"{h.path}:{h.start_line}-{h.end_line}", snippet=_snippet(h.content), url=h.url,
                     path=h.path, start_line=h.start_line, end_line=h.end_line, score=round(h.score, 5))
        for h in hits])


def _snippet(content: str, max_lines: int = 12) -> str:
    lines = content.split("\n")
    return "\n".join(lines[:max_lines]) + ("\n…" if len(lines) > max_lines else "")


async def _search_docs(db: DB, ws: Workspace, repo_ids: list[uuid.UUID], q: str) -> list[SearchHitOut]:
    if not repo_ids:
        return []
    rows = (await db.execute(text("""
        SELECT 'doc' AS kind, d.id AS doc_id, d.repo_id, r.full_name, d.title,
               ts_headline('english', v.content_md, websearch_to_tsquery('english', :q),
                           'MaxFragments=2, MinWords=8, MaxWords=30') AS snippet,
               ts_rank_cd(v.tsv, websearch_to_tsquery('english', :q)) AS rank
        FROM documents d
        JOIN document_versions v ON v.id = d.published_version_id
        JOIN repositories r ON r.id = d.repo_id
        WHERE d.workspace_id = :ws AND d.repo_id = ANY(:repos) AND v.tsv @@ websearch_to_tsquery('english', :q)
        UNION ALL
        SELECT 'changelog', NULL, c.repo_id, r.full_name, 'Changelog ' || left(c.to_sha, 7),
               ts_headline('english', c.content_md, websearch_to_tsquery('english', :q)),
               ts_rank_cd(c.tsv, websearch_to_tsquery('english', :q))
        FROM changelog_entries c JOIN repositories r ON r.id = c.repo_id
        WHERE c.workspace_id = :ws AND c.repo_id = ANY(:repos) AND c.status = 'published'
          AND c.tsv @@ websearch_to_tsquery('english', :q)
        ORDER BY rank DESC LIMIT 20
    """), {"q": q, "ws": ws.id, "repos": repo_ids})).all()
    return [SearchHitOut(kind=r.kind, repo_id=r.repo_id, repo_full_name=r.full_name, title=r.title,
                         snippet=r.snippet, url=None, doc_id=r.doc_id, score=round(float(r.rank), 5)) for r in rows]


# ----------------------------------------------------------------------------- chat


def _sse(event: str, data: Any) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n".encode()


@router.post("/workspaces/{ws}/chat", summary="Ask a question; streams Server-Sent Events",
             responses={200: {"content": {"text/event-stream": {}}}})
async def chat(ws: str, body: ChatIn, db: DB, principal: CurrentPrincipal) -> StreamingResponse:
    s = get_settings()
    w = await get_workspace(db, principal, ws)
    if not (w.settings or {}).get("chat_enabled", True):
        raise Problem(403, "Forbidden", "Chat is disabled for this workspace.", code="chat_disabled")
    await _quota(principal, w, "chat")
    try:
        await check_budget(db, w.id)
    except BudgetExceeded as exc:
        CHAT_REQUESTS.labels("limited").inc()
        raise Problem(429, "Too many requests", "The AI budget for today is used up. Try again tomorrow.",
                      code="ai_budget") from exc

    thread: ChatThread
    if body.thread_id is not None:
        thread, _ = await load_for_user(db, ChatThread, body.thread_id, principal)
        if thread.user_id != (principal.user.id if principal.user else None) or thread.workspace_id != w.id:
            raise not_found("Thread")
    else:
        thread = ChatThread(workspace_id=w.id, user_id=principal.user.id if principal.user else None,
                            title=body.message.strip()[:120])
        db.add(thread)
        await db.flush()
    history_rows = (await db.execute(select(ChatMessage).where(ChatMessage.thread_id == thread.id)
                                     .order_by(ChatMessage.created_at.desc()).limit(HISTORY_TURNS * 2))).scalars().all()
    user_msg = ChatMessage(workspace_id=w.id, thread_id=thread.id, role="user", content=body.message.strip())
    db.add(user_msg)
    repo_ids = await _repo_ids(db, w, body.repo_ids)
    embedder = get_embedder()
    hits, has_context = await retrieve(db, workspace_id=w.id, repo_ids=repo_ids, query=body.message,
                                       embedder=embedder)
    await db.commit()  # thread + user message persist even if streaming fails

    history: list[dict[str, Any]] = []
    size = 0
    for m in reversed(history_rows):
        size += len(m.content)
        if size > HISTORY_CHARS:
            break
        history.append({"role": m.role, "content": m.content})
    thread_id, ws_id = thread.id, w.id
    sources = [h.as_source(i) for i, h in enumerate(hits, 1)]

    async def events() -> AsyncIterator[bytes]:
        yield _sse("meta", {"thread_id": str(thread_id)})
        if not has_context:
            CHAT_REQUESTS.labels("no_context").inc()
            yield _sse("token", {"text": NO_CONTEXT})
            await _save_answer(ws_id, thread_id, NO_CONTEXT, [], None, None)
            yield _sse("done", {"thread_id": str(thread_id)})
            return
        prompt = f"{build_sources_block(hits)}\n\nQuestion: {body.message.strip()}"
        usage = Usage()
        answer: list[str] = []
        queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()

        async def produce() -> None:
            try:
                async for tok in get_llm().stream(task="chat", model=s.llm_model_chat, system=CHAT_SYSTEM,
                                                  messages=[*history, {"role": "user", "content": prompt}],
                                                  max_tokens=1500, usage_out=usage):
                    await queue.put(("token", tok))
                await queue.put(("end", None))
            except LLMRefusal:
                await queue.put(("error", "The AI declined to answer this question."))
            except Exception as exc:
                log.warning("chat.llm_failed", error=type(exc).__name__)
                await queue.put(("error", "The AI service is unavailable right now. Please try again."))

        task = asyncio.create_task(produce())
        try:
            while True:
                try:
                    kind, val = await asyncio.wait_for(queue.get(), timeout=KEEPALIVE_S)
                except TimeoutError:
                    yield b": keep-alive\n\n"
                    continue
                if kind == "token":
                    answer.append(val)
                    yield _sse("token", {"text": val})
                elif kind == "error":
                    CHAT_REQUESTS.labels("error").inc()
                    yield _sse("error", {"message": val})
                    break
                else:
                    CHAT_REQUESTS.labels("answered").inc()
                    yield _sse("sources", sources)
                    break
        finally:
            if not task.done():
                task.cancel()
                with contextlib.suppress(BaseException):
                    await task
            text_ = "".join(answer).strip()
            if text_:
                await _save_answer(ws_id, thread_id, text_, sources, s.llm_model_chat, usage)
        yield _sse("done", {"thread_id": str(thread_id)})

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


async def _save_answer(ws_id: uuid.UUID, thread_id: uuid.UUID, content: str, sources: list[dict[str, Any]],
                       model: str | None, usage: Usage | None) -> None:
    try:
        async with session_scope() as db:
            db.add(ChatMessage(workspace_id=ws_id, thread_id=thread_id, role="assistant", content=content,
                               sources=sources))
            if model and usage:
                record_llm(db, workspace_id=ws_id, job_id=None, purpose="chat", model=model, usage=usage)
    except Exception as exc:
        log.warning("chat.save_failed", error=type(exc).__name__)


@router.get("/workspaces/{ws}/chat/threads", response_model=list[ThreadOut])
async def threads(ws: str, db: DB, principal: UserPrincipal) -> list[ThreadOut]:
    w = await get_workspace(db, principal, ws)
    rows = (await db.execute(select(ChatThread).where(ChatThread.workspace_id == w.id,
                                                      ChatThread.user_id == principal.user_id)
                             .order_by(ChatThread.created_at.desc()).limit(50))).scalars()
    return [ThreadOut.model_validate(t) for t in rows]


async def _own_thread(db: DB, principal: Principal, thread_id: uuid.UUID) -> ChatThread:
    thread, _ = await load_for_user(db, ChatThread, thread_id, principal)
    if thread.user_id is None or principal.user is None or thread.user_id != principal.user.id:
        raise not_found("Thread")
    return thread


@router.get("/chat/threads/{thread_id}", response_model=ThreadDetailOut)
async def get_thread(thread_id: uuid.UUID, db: DB, principal: UserPrincipal) -> ThreadDetailOut:
    thread = await _own_thread(db, principal, thread_id)
    msgs = (await db.execute(select(ChatMessage).where(ChatMessage.thread_id == thread.id)
                             .order_by(ChatMessage.created_at))).scalars()
    return ThreadDetailOut(id=thread.id, title=thread.title, created_at=thread.created_at,
                           messages=[ChatMessageOut.model_validate(m) for m in msgs])


@router.delete("/chat/threads/{thread_id}", response_model=Ok)
async def delete_thread(thread_id: uuid.UUID, db: DB, principal: UserPrincipal) -> Ok:
    thread = await _own_thread(db, principal, thread_id)
    await db.delete(thread)
    return Ok()
