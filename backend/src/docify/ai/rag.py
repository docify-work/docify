"""Hybrid retrieval: exact vector scan + full-text search, merged with RRF (Master Doc §11.4, D19)."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from docify.ai.budget import estimate_tokens
from docify.ai.chunking import split_identifiers
from docify.ai.citations import permalink
from docify.ai.embeddings import Embedder

TOP_K = 40
RRF_K = 60
FINAL_K = 8
MAX_PER_FILE = 2
MAX_CONTEXT_TOKENS = 6000

STOPWORDS = frozenset(
    "a an and are as at be but by can do does for from how i in is it its me my of on or our should so that the "
    "their them then there these this to us was we what when where which who why will with you your did done has "
    "have had into about please tell show explain find code file files function work works".split()
)
_WORD = re.compile(r"[A-Za-z0-9_]+")
_PATHLIKE = re.compile(r"[\w-]+/[\w./-]+|\b[\w-]+\.(py|ts|tsx|js|go|rs|java|rb|md|ya?ml|json|toml|tf)\b")


@dataclass
class Hit:
    chunk_id: uuid.UUID
    repo_id: uuid.UUID
    path: str
    start_line: int
    end_line: int
    commit_sha: str
    content: str
    repo_full_name: str
    similarity: float | None = None
    fts_rank: float | None = None
    score: float = 0.0
    sources: list[str] = field(default_factory=list)

    @property
    def url(self) -> str:
        return permalink(self.repo_full_name, self.commit_sha, self.path, self.start_line, self.end_line)

    def as_source(self, n: int) -> dict[str, Any]:
        return {"n": n, "repo_id": str(self.repo_id), "repo": self.repo_full_name, "path": self.path,
                "start_line": self.start_line, "end_line": self.end_line, "commit_sha": self.commit_sha,
                "url": self.url}


_SUFFIXES = ("ing", "ers", "ies", "ed", "es", "er", "s")


def _stem(word: str) -> str | None:
    """Tiny suffix stripper: `hashed` → `hash`, `passwords` → `password`. The 'simple' FTS config
    doesn't stem (good for identifiers), so we add `stem:*` prefix terms for natural-language questions."""
    for suf in _SUFFIXES:
        if word.endswith(suf) and len(word) - len(suf) >= 4:
            return word[: -len(suf)]
    return None


def _terms(q: str) -> list[str]:
    words = {w.lower() for w in _WORD.findall(split_identifiers(q))}
    return sorted(w for w in words if w not in STOPWORDS and len(w) > 1 and not w.isdigit())[:20]


def term_coverage(q: str, text_: str) -> float:
    """Share of the question's key terms (or their stems) found in a chunk."""
    terms = _terms(q)
    if not terms:
        return 0.0
    hay = split_identifiers(text_).lower()
    found = sum(1 for t in terms if t in hay or ((st := _stem(t)) is not None and st in hay))
    return found / len(terms)


def fts_query(q: str) -> str | None:
    """'How are passwords hashed?' → 'hash:* | hashed | password:* | passwords' (OR of meaningful terms)."""
    terms = _terms(q)
    parts: set[str] = set()
    for t in terms:
        parts.add(t)
        stem = _stem(t)
        if stem:
            parts.add(f"{stem}:*")
    return " | ".join(sorted(parts)) if parts else None


_VEC_SQL = text("""
SELECT c.id, c.repo_id, c.path, c.start_line, c.end_line, c.commit_sha, c.content, r.full_name,
       1 - (c.embedding <=> CAST(:q AS vector)) AS sim
FROM chunks c JOIN repositories r ON r.id = c.repo_id
WHERE c.workspace_id = :ws AND c.repo_id = ANY(:repos) AND c.embed_model = :model AND c.embedding IS NOT NULL
ORDER BY c.embedding <=> CAST(:q AS vector)
LIMIT :k
""")

_FTS_SQL = text("""
SELECT c.id, c.repo_id, c.path, c.start_line, c.end_line, c.commit_sha, c.content, r.full_name,
       ts_rank_cd(c.tsv, to_tsquery('simple', :tsq)) AS rank
FROM chunks c JOIN repositories r ON r.id = c.repo_id
WHERE c.workspace_id = :ws AND c.repo_id = ANY(:repos) AND c.tsv @@ to_tsquery('simple', :tsq)
ORDER BY rank DESC
LIMIT :k
""")

_PATH_SQL = text("""
SELECT c.id, c.repo_id, c.path, c.start_line, c.end_line, c.commit_sha, c.content, r.full_name,
       similarity(c.path, :p) AS rank
FROM chunks c JOIN repositories r ON r.id = c.repo_id
WHERE c.workspace_id = :ws AND c.repo_id = ANY(:repos) AND c.path % :p
ORDER BY rank DESC, c.start_line
LIMIT 10
""")


def _hit(row: Any) -> Hit:
    return Hit(row.id, row.repo_id, row.path, row.start_line, row.end_line, row.commit_sha, row.content, row.full_name)


async def retrieve(db: AsyncSession, *, workspace_id: uuid.UUID, repo_ids: list[uuid.UUID], query: str,
                   embedder: Embedder | None, query_vector: list[float] | None = None) -> tuple[list[Hit], bool]:
    """Returns (top hits, has_context). `has_context=False` → answer "I don't know" without an LLM call."""
    from docify.config import get_settings

    if not repo_ids:
        return [], False
    hits: dict[uuid.UUID, Hit] = {}
    best_sim = 0.0
    vec = query_vector
    if vec is None and embedder is not None:
        try:
            vec = (await embedder.embed([query], input_type="query"))[0][0]
        except Exception:
            vec = None  # F22: embeddings down → FTS only
    if vec is not None and embedder is not None:
        rows = (await db.execute(_VEC_SQL, {"q": str(vec), "ws": workspace_id, "repos": repo_ids,
                                            "model": embedder.model, "k": TOP_K})).all()
        for rank, row in enumerate(rows, 1):
            h = hits.setdefault(row.id, _hit(row))
            h.similarity = float(row.sim)
            h.score += 1.0 / (RRF_K + rank)
            h.sources.append("vector")
            best_sim = max(best_sim, float(row.sim))
    fts_hits = 0
    tsq = fts_query(query)
    if tsq:
        rows = (await db.execute(_FTS_SQL, {"tsq": tsq, "ws": workspace_id, "repos": repo_ids, "k": TOP_K})).all()
        # A lexical hit only counts as "context" if one chunk covers most of the question's key terms;
        # a single shared common word ("name", "events") is not evidence.
        fts_hits = sum(1 for row in rows[:10] if term_coverage(query, f"{row.path} {row.content}") >= 0.5)
        for rank, row in enumerate(rows, 1):
            h = hits.setdefault(row.id, _hit(row))
            h.fts_rank = float(row.rank)
            h.score += 1.0 / (RRF_K + rank)
            h.sources.append("fts")
    m = _PATHLIKE.search(query)
    if m:
        rows = (await db.execute(_PATH_SQL, {"p": m.group(0), "ws": workspace_id, "repos": repo_ids})).all()
        fts_hits += len(rows)
        for rank, row in enumerate(rows, 1):
            h = hits.setdefault(row.id, _hit(row))
            h.score += 1.0 / (RRF_K + rank)
            h.sources.append("path")

    has_context = best_sim >= get_settings().rag_min_sim or fts_hits > 0
    ranked = sorted(hits.values(), key=lambda h: h.score, reverse=True)
    out: list[Hit] = []
    per_file: dict[str, int] = {}
    tokens = 0
    for h in ranked:
        key = f"{h.repo_id}:{h.path}"
        if per_file.get(key, 0) >= MAX_PER_FILE:
            continue
        t = estimate_tokens(h.content)
        if tokens + t > MAX_CONTEXT_TOKENS and out:
            continue
        out.append(h)
        per_file[key] = per_file.get(key, 0) + 1
        tokens += t
        if len(out) >= FINAL_K:
            break
    return out, has_context and bool(out)


def build_sources_block(hits: list[Hit]) -> str:
    parts = []
    for i, h in enumerate(hits, 1):
        parts.append(f'<source id="{i}" repo="{h.repo_full_name}" path="{h.path}" lines="{h.start_line}-{h.end_line}">'
                     f"\n{h.content}\n</source>")
    return "\n\n".join(parts)
