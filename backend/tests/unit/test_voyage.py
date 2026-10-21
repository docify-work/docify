from __future__ import annotations

import json

import httpx
import pytest
import respx

from docify.ai.embeddings import VoyageEmbedder
from docify.jobs.errors import NonRetryableError, RetryableError


@respx.mock
async def test_embed_batches_and_orders() -> None:
    calls: list[dict] = []  # type: ignore[type-arg]

    def reply(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(body)
        data = [{"object": "embedding", "index": i, "embedding": [float(i), 1.0]} for i in range(len(body["input"]))]
        return httpx.Response(200, json={"data": list(reversed(data)), "usage": {"total_tokens": 3}})

    respx.post(VoyageEmbedder.URL).mock(side_effect=reply)
    e = VoyageEmbedder("k", "voyage-code-3", 2)
    vecs, tokens = await e.embed([f"t{i}" for i in range(130)], input_type="document")
    assert len(vecs) == 130
    assert vecs[1] == [1.0, 1.0]  # re-ordered by index
    assert tokens == 6  # two batches (128 + 2)
    assert calls[0]["input_type"] == "document"
    assert calls[0]["output_dimension"] == 2


@respx.mock
@pytest.mark.parametrize(("status", "exc"), [(429, RetryableError), (503, RetryableError), (401, NonRetryableError)])
async def test_errors(status: int, exc: type[Exception]) -> None:
    respx.post(VoyageEmbedder.URL).mock(return_value=httpx.Response(status, json={"detail": "nope"}))
    with pytest.raises(exc):
        await VoyageEmbedder("k", "voyage-code-3", 2).embed(["x"], input_type="query")
