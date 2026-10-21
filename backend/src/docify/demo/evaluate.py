"""`docify eval`: retrieval quality on a fixture repo (Master Doc §11.7).

Metrics:
- hit@8: share of answerable questions whose expected file is in the top 8 chunks
- unanswerable-correct: share of unanswerable questions where the no-context gate fires
Used to tune RAG_MIN_SIM. With AI_MODE=real it costs a few cents of embeddings (no LLM calls).
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select

from docify.ai.embeddings import get_embedder
from docify.ai.rag import retrieve
from docify.config import get_settings
from docify.db.models import Repository, Workspace
from docify.db.session import session_scope


def bundled_dir() -> Path:
    return Path(str(resources.files("docify.demo").joinpath("eval_data")))


async def run_eval(questions_path: str | None, workspace: str | None, min_hit: float) -> bool:
    path = Path(questions_path) if questions_path else bundled_dir() / "questions.yaml"
    data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    slug = workspace or get_settings().demo_workspace_slug
    embedder = get_embedder()
    hits = answerable = unans_ok = unanswerable = 0
    async with session_scope() as db:
        ws = (await db.execute(select(Workspace).where(Workspace.slug == slug))).scalar_one_or_none()
        if ws is None:
            print(f"workspace {slug!r} not found; run `docify seed-demo --from-dir <fixture>` first")
            return False
        repo_ids = list((await db.execute(select(Repository.id).where(Repository.workspace_id == ws.id,
                                                                      Repository.status == "ready"))).scalars())
        for q in data.get("questions", []):
            found, has_ctx = await retrieve(db, workspace_id=ws.id, repo_ids=repo_ids, query=q["q"], embedder=embedder)
            paths = [h.path for h in found]
            if q.get("expect"):
                answerable += 1
                ok = any(p.endswith(q["expect"]) for p in paths)
                hits += ok
                print(f"{'HIT ' if ok else 'MISS'} {q['q']!r} expect={q['expect']} got={paths[:3]}")
            else:
                unanswerable += 1
                ok = not has_ctx
                unans_ok += ok
                print(f"{'OK  ' if ok else 'FAIL'} (unanswerable) {q['q']!r} gate={'closed' if ok else 'open'}")
    hit_rate = hits / answerable if answerable else 0.0
    unans_rate = unans_ok / unanswerable if unanswerable else 1.0
    print(f"\nhit@8 = {hit_rate:.2f} ({hits}/{answerable}) · unanswerable-correct = {unans_rate:.2f} "
          f"({unans_ok}/{unanswerable}) · RAG_MIN_SIM={get_settings().rag_min_sim} · embedder={embedder.model}")
    return hit_rate >= min_hit
