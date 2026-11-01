"""BedrockLLM + BedrockTitanEmbedder (D61) with botocore's Stubber - no AWS calls."""

from __future__ import annotations

import io
import json

import pytest
from botocore.stub import Stubber

from docify.ai.embeddings import BedrockTitanEmbedder
from docify.ai.llm import BedrockLLM, LLMRefusal, LLMTruncated, Usage, cost_usd
from docify.jobs.errors import NonRetryableError, RetryableError

MODEL = "apac.amazon.nova-micro-v1:0"
SCHEMA = {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]}


@pytest.fixture
def llm(monkeypatch: pytest.MonkeyPatch) -> BedrockLLM:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    return BedrockLLM("ap-south-1")


def _reply(content: list[dict], stop: str = "end_turn", tokens: tuple[int, int] = (100, 20)) -> dict:
    return {"output": {"message": {"role": "assistant", "content": content}}, "stopReason": stop,
            "usage": {"inputTokens": tokens[0], "outputTokens": tokens[1], "totalTokens": sum(tokens)},
            "metrics": {"latencyMs": 10}}


async def test_complete_json_via_forced_tool(llm: BedrockLLM) -> None:
    with Stubber(llm.client) as stub:
        stub.add_response("converse", _reply([{"toolUse": {"toolUseId": "t1", "name": "respond",
                                                            "input": {"summary": "splits a bill"}}}], "tool_use"))
        r = await llm.complete(task="summary", model=MODEL, system="sys",
                               messages=[{"role": "user", "content": "code"}], max_tokens=100, output_schema=SCHEMA)
    assert r.data == {"summary": "splits a bill"}
    assert json.loads(r.text) == r.data
    assert (r.usage.input_tokens, r.usage.output_tokens) == (100, 20)


async def test_params_force_the_tool_and_convert_messages() -> None:
    p = BedrockLLM._params("doc", MODEL, "sys", [{"role": "user", "content": [{"type": "text", "text": "hi"}]}],
                           50, SCHEMA)
    assert p["messages"] == [{"role": "user", "content": [{"text": "hi"}]}]
    assert p["toolConfig"]["toolChoice"] == {"tool": {"name": "respond"}}
    assert p["toolConfig"]["tools"][0]["toolSpec"]["inputSchema"] == {"json": SCHEMA}
    assert "toolConfig" not in BedrockLLM._params("chat", MODEL, "sys", [{"role": "user", "content": "x"}], 50, None)


async def test_plain_text_completion(llm: BedrockLLM) -> None:
    with Stubber(llm.client) as stub:
        stub.add_response("converse", _reply([{"text": "Hello "}, {"text": "world"}]))
        r = await llm.complete(task="chat", model=MODEL, system="s", messages=[{"role": "user", "content": "x"}],
                               max_tokens=10)
    assert (r.text, r.data, r.stop_reason) == ("Hello world", None, "end_turn")


@pytest.mark.parametrize(("stop", "exc"), [("max_tokens", LLMTruncated), ("content_filtered", LLMRefusal),
                                           ("guardrail_intervened", LLMRefusal)])
async def test_stop_reasons(llm: BedrockLLM, stop: str, exc: type[Exception]) -> None:
    with Stubber(llm.client) as stub:
        stub.add_response("converse", _reply([{"text": "partial"}], stop))
        with pytest.raises(exc) as info:
            await llm.complete(task="doc", model=MODEL, system="s", messages=[{"role": "user", "content": "x"}],
                               max_tokens=10)
    assert info.value.usage.input_tokens == 100  # billed usage is still reported


@pytest.mark.parametrize(("code", "exc"), [("ThrottlingException", RetryableError),
                                           ("ServiceUnavailableException", RetryableError),
                                           ("AccessDeniedException", NonRetryableError),
                                           ("ValidationException", NonRetryableError)])
async def test_error_mapping(llm: BedrockLLM, code: str, exc: type[Exception]) -> None:
    with Stubber(llm.client) as stub:
        stub.add_client_error("converse", service_error_code=code, service_message="nope")
        with pytest.raises(exc):
            await llm.complete(task="chat", model=MODEL, system="s", messages=[{"role": "user", "content": "x"}],
                               max_tokens=10)


def test_nova_and_titan_prices_registered() -> None:
    # Budget enforcement depends on these: an unknown model would count as $0.
    assert cost_usd(MODEL, Usage(1_000_000, 1_000_000)) == pytest.approx(0.041 + 0.164)
    assert cost_usd("apac.amazon.nova-lite-v1:0", Usage(1_000_000, 0)) == pytest.approx(0.071)


async def test_titan_embed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    e = BedrockTitanEmbedder("ap-south-1", "amazon.titan-embed-text-v2:0", 1024)
    with Stubber(e.client) as stub:
        for n in (3, 4):
            body = json.dumps({"embedding": [0.1] * 1024, "inputTextTokenCount": n}).encode()
            stub.add_response("invoke_model", {"body": io.BytesIO(body), "contentType": "application/json"})
        vectors, tokens = await e.embed(["a", "b"], input_type="document")
    assert len(vectors) == 2 and len(vectors[0]) == 1024
    assert tokens == 7


def test_titan_rejects_unsupported_dim() -> None:
    with pytest.raises(ValueError, match="256, 512 or 1024"):
        BedrockTitanEmbedder("ap-south-1", "amazon.titan-embed-text-v2:0", 768)
