"""Embeddings behind an interface (D18, D61): Voyage `voyage-code-3`, Amazon Titan V2 (Bedrock) or a fake."""

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


class BedrockTitanEmbedder:
    """Amazon Titan Text Embeddings V2 via Bedrock InvokeModel (D61). One text per request (the API has no
    batch endpoint), so requests run concurrently in worker threads, at most `parallel` at a time.

    Body: {"inputText", "dimensions": 256|512|1024, "normalize": true}. Titan has no query/document
    distinction, so `input_type` is ignored. Inputs are capped at 40k chars (model limit 8k tokens / 50k chars).
    """

    MAX_CHARS = 40_000

    def __init__(self, region: str, model: str, dim: int, parallel: int = 8) -> None:
        import boto3
        import botocore.config
        import botocore.exceptions

        if dim not in (256, 512, 1024):
            raise ValueError("Titan V2 supports 256, 512 or 1024 dimensions")
        self._errors = botocore.exceptions
        cfg = botocore.config.Config(retries={"max_attempts": 3, "mode": "standard"}, read_timeout=60,
                                     max_pool_connections=parallel)
        self.client = boto3.client("bedrock-runtime", region_name=region, config=cfg)
        self.model, self.dim, self.parallel = model, dim, parallel

    def _one(self, text: str) -> tuple[list[float], int]:
        import json

        body = json.dumps({"inputText": text[:self.MAX_CHARS] or " ", "dimensions": self.dim, "normalize": True})
        try:
            r = self.client.invoke_model(modelId=self.model, body=body, contentType="application/json",
                                         accept="application/json")
        except self._errors.ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in ("ThrottlingException", "ServiceUnavailableException", "ModelTimeoutException",
                        "InternalServerException"):
                raise RetryableError(f"embedding provider {code}", delay_s=30) from exc
            raise NonRetryableError(f"Embedding request rejected ({code})", code="embed_error") from exc
        except (self._errors.EndpointConnectionError, self._errors.ReadTimeoutError) as exc:
            raise RetryableError("embedding provider unavailable") from exc
        out = json.loads(r["body"].read())
        return [float(x) for x in out["embedding"]], int(out.get("inputTextTokenCount", 0))

    async def embed(self, texts: list[str], *, input_type: Literal["document", "query"]) -> tuple[
        list[list[float]], int]:
        import asyncio

        sem = asyncio.Semaphore(self.parallel)

        async def run(t: str) -> tuple[list[float], int]:
            async with sem:
                return await asyncio.to_thread(self._one, t)

        results = await asyncio.gather(*(run(t) for t in texts))
        return [v for v, _ in results], sum(n for _, n in results)


_embedder: Embedder | None = None


def get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        s = get_settings()
        if s.ai_mode == "real" and s.ai_provider == "bedrock":
            _embedder = BedrockTitanEmbedder(s.bedrock_region, s.embed_model, s.embed_dim)
        elif s.ai_mode == "real":
            _embedder = VoyageEmbedder(s.voyage_api_key.get_secret_value(), s.embed_model, s.embed_dim)
        else:
            from docify.ai.fakes import FakeEmbedder

            _embedder = FakeEmbedder(dim=s.embed_dim)
    return _embedder


def set_embedder(embedder: Embedder | None) -> None:
    global _embedder
    _embedder = embedder
