"""Embeddings behind an interface (D18): Voyage `voyage-code-3` (1024-d) or a deterministic fake."""

from __future__ import annotations

from typing import Literal, Protocol

from docify.config import get_settings
from docify.jobs.errors import NonRetryableError, RetryableError

BATCH = 128


class Embedder(Protocol):
    model: str
    dim: int

    async def embed(self, texts: list[str], *, input_type: Literal["document", "query"]) -> tuple[
        list[list[float]], int]:
        """Returns (vectors, total_tokens)."""
        ...


class VoyageEmbedder:
    """Voyage REST API via httpx (the official SDK drags in numpy/pillow/tokenizers ≈ 150 MB we don't need).

    POST https://api.voyageai.com/v1/embeddings {input, model, input_type, output_dimension, truncation}
    """

    URL = "https://api.voyageai.com/v1/embeddings"

    def __init__(self, api_key: str, model: str, dim: int) -> None:
        import httpx

        self.client = httpx.AsyncClient(timeout=60, headers={"Authorization": f"Bearer {api_key}"})
        self.model, self.dim = model, dim

    async def embed(self, texts: list[str], *, input_type: Literal["document", "query"]) -> tuple[
        list[list[float]], int]:
        import httpx

        vectors: list[list[float]] = []
        tokens = 0
        for i in range(0, len(texts), BATCH):
            batch = texts[i:i + BATCH]
            try:
                r = await self.client.post(self.URL, json={"input": batch, "model": self.model,
                                                           "input_type": input_type, "truncation": True,
                                                           "output_dimension": self.dim})
            except httpx.HTTPError as exc:
                raise RetryableError("embedding provider unavailable") from exc
            if r.status_code == 429:
                raise RetryableError("embedding rate limited", delay_s=int(r.headers.get("retry-after", "60")))
            if r.status_code >= 500:
                raise RetryableError(f"embedding provider HTTP {r.status_code}")
            if r.status_code >= 400:
                detail = str(r.json().get("detail", ""))[:200] if r.headers.get("content-type", "").startswith(
                    "application/json") else ""
                raise NonRetryableError(f"Embedding request rejected ({r.status_code}): {detail}", code="embed_error")
            body = r.json()
            data = sorted(body["data"], key=lambda d: d["index"])
            vectors.extend([[float(x) for x in d["embedding"]] for d in data])
            tokens += int((body.get("usage") or {}).get("total_tokens", 0))
        return vectors, tokens


_embedder: Embedder | None = None


def get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        s = get_settings()
        if s.ai_mode == "real":
            _embedder = VoyageEmbedder(s.voyage_api_key.get_secret_value(), s.embed_model, s.embed_dim)
        else:
            from docify.ai.fakes import FakeEmbedder

            _embedder = FakeEmbedder(dim=s.embed_dim)
    return _embedder


def set_embedder(embedder: Embedder | None) -> None:
    global _embedder
    _embedder = embedder
