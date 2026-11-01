"""LLM interface + Anthropic implementation (Master Doc §11.1).

Rules followed (from the claude-api skill, re-read 2026-10-21):
- official `anthropic` SDK only; exact model ids (no date suffix)
- no assistant prefill; JSON via `output_config.format` (json_schema)
- always check `stop_reason` (`refusal`, `max_tokens`) before using content
- `output_config.effort`: low for summaries/chat, medium for doc synthesis
- prompt caching on the stable prefix (system prompt)
- typed exceptions caught most-specific first
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from docify.config import get_settings
from docify.jobs.errors import NonRetryableError, RetryableError

Task = Literal["summary", "doc", "changelog", "chat", "eval"]


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


@dataclass
class LLMResult:
    text: str
    data: dict[str, Any] | None
    stop_reason: str
    model: str
    usage: Usage = field(default_factory=Usage)


class LLMStop(Exception):
    """Base for "the call happened (and was billed) but gave no usable output"."""

    def __init__(self, model: str, usage: Usage | None = None) -> None:
        super().__init__(model)
        self.model = model
        self.usage = usage or Usage()


class LLMRefusal(LLMStop):
    """The model declined (stop_reason=refusal). Handled per F19: section skipped, job continues."""


class LLMTruncated(LLMStop):
    """stop_reason=max_tokens. Caller may retry once with fewer inputs (F19)."""


# USD per million tokens: (input ≤100K prompt, output, input >100K prompt, output >100K prompt).
PRICES: dict[str, tuple[float, float, float, float]] = {
    "claude-haiku-5-5": (0.10, 0.50, 0.50, 2.50),
    "claude-sonnet-5-5": (2.00, 10.00, 2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00, 4.00, 20.00),
    # Amazon Nova via Bedrock, ap-south-1 on-demand (AWS Price List API, 2026-11-01). The apac.* cross-region
    # inference profiles are billed at the source-region (Mumbai) price. No long-context surcharge.
    "apac.amazon.nova-micro-v1:0": (0.041, 0.164, 0.041, 0.164),
    "apac.amazon.nova-lite-v1:0": (0.071, 0.284, 0.071, 0.284),
    "apac.amazon.nova-pro-v1:0": (0.94, 3.76, 0.94, 3.76),
}
EMBED_PRICES = {"voyage-code-3": 0.18, "amazon.titan-embed-text-v2:0": 0.024, "fake-embed": 0.0}


def cost_usd(model: str, usage: Usage) -> float:
    if model not in PRICES:
        return 0.0
    in_small, out_small, in_big, out_big = PRICES[model]
    prompt = usage.input_tokens + usage.cache_read_tokens + usage.cache_write_tokens
    p_in, p_out = (in_small, out_small) if prompt <= 100_000 else (in_big, out_big)
    return (usage.input_tokens * p_in + usage.cache_write_tokens * p_in * 1.25
            + usage.cache_read_tokens * p_in * 0.1 + usage.output_tokens * p_out) / 1_000_000


class LLM(Protocol):
    async def complete(self, *, task: Task, model: str, system: str, messages: list[dict[str, Any]],
                       max_tokens: int, output_schema: dict[str, Any] | None = None) -> LLMResult: ...

    def stream(self, *, task: Task, model: str, system: str, messages: list[dict[str, Any]],
               max_tokens: int, usage_out: Usage) -> AsyncIterator[str]: ...


_EFFORT: dict[str, str] = {"summary": "low", "changelog": "low", "chat": "low", "doc": "medium", "eval": "low"}


class AnthropicLLM:
    def __init__(self, api_key: str) -> None:
        import anthropic

        self._anthropic = anthropic
        self.client = anthropic.AsyncAnthropic(api_key=api_key, max_retries=2, timeout=120.0)

    def _params(self, task: Task, model: str, system: str, messages: list[dict[str, Any]],
                max_tokens: int, output_schema: dict[str, Any] | None) -> dict[str, Any]:
        output_config: dict[str, Any] = {"effort": _EFFORT[task]}
        if output_schema is not None:
            output_config["format"] = {"type": "json_schema", "schema": output_schema}
        params: dict[str, Any] = {
            "model": model, "max_tokens": max_tokens, "messages": messages,
            # Stable system prompt first → cacheable prefix.
            "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            "output_config": output_config,
        }
        if task in ("summary", "chat", "changelog"):
            # Cheap, latency-sensitive calls: skip thinking (allowed at effort ≤ high on Haiku 5.5).
            params["thinking"] = {"type": "disabled"}
        return params

    def _map_error(self, exc: Exception) -> Exception:
        a = self._anthropic
        if isinstance(exc, a.RateLimitError):
            retry_after = exc.response.headers.get("retry-after")
            return RetryableError("LLM rate limited", delay_s=int(retry_after) + 5 if retry_after else None)
        if isinstance(exc, (a.AuthenticationError, a.PermissionDeniedError)):
            return NonRetryableError("AI provider rejected our API key.", code="ai_auth")
        if isinstance(exc, a.BadRequestError):
            return NonRetryableError(f"AI request was invalid: {exc.message[:200]}", code="ai_bad_request")
        if isinstance(exc, a.APIStatusError):
            return RetryableError(f"LLM HTTP {exc.status_code}") if exc.status_code >= 500 or exc.status_code == 529 \
                else NonRetryableError(f"AI error {exc.status_code}", code="ai_error")
        if isinstance(exc, (a.APIConnectionError, a.APITimeoutError)):
            return RetryableError("LLM connection error")
        return exc

    async def complete(self, *, task: Task, model: str, system: str, messages: list[dict[str, Any]],
                       max_tokens: int, output_schema: dict[str, Any] | None = None) -> LLMResult:
        try:
            resp = await self.client.messages.create(**self._params(task, model, system, messages, max_tokens,
                                                                    output_schema))
        except self._anthropic.AnthropicError as exc:
            raise self._map_error(exc) from exc
        u = resp.usage
        usage = Usage(u.input_tokens or 0, u.output_tokens or 0, getattr(u, "cache_read_input_tokens", 0) or 0,
                      getattr(u, "cache_creation_input_tokens", 0) or 0)
        if resp.stop_reason == "refusal":
            raise LLMRefusal(model, usage)
        text = "".join(b.text for b in resp.content if b.type == "text")
        if resp.stop_reason == "max_tokens":
            raise LLMTruncated(model, usage)
        data = None
        if output_schema is not None:
            try:
                data = json.loads(text)
            except json.JSONDecodeError as exc:
                raise RetryableError("LLM returned invalid JSON") from exc
        return LLMResult(text=text, data=data, stop_reason=resp.stop_reason or "end_turn", model=model, usage=usage)

    async def stream(self, *, task: Task, model: str, system: str, messages: list[dict[str, Any]],
                     max_tokens: int, usage_out: Usage) -> AsyncIterator[str]:
        # Usage is captured from the events as they arrive, so a client disconnect or mid-stream error
        # still records what was billed (message_start → input tokens, message_delta → output tokens).
        stop_reason = None
        try:
            async with self.client.messages.stream(**self._params(task, model, system, messages, max_tokens,
                                                                  None)) as stream:
                async for event in stream:
                    if event.type == "message_start":
                        u = event.message.usage
                        usage_out.input_tokens = u.input_tokens or 0
                        usage_out.cache_read_tokens = getattr(u, "cache_read_input_tokens", 0) or 0
                        usage_out.cache_write_tokens = getattr(u, "cache_creation_input_tokens", 0) or 0
                    elif event.type == "content_block_delta" and event.delta.type == "text_delta":
                        yield event.delta.text
                    elif event.type == "message_delta":
                        usage_out.output_tokens = event.usage.output_tokens or usage_out.output_tokens
                        stop_reason = event.delta.stop_reason
        except self._anthropic.AnthropicError as exc:
            raise self._map_error(exc) from exc
        if stop_reason == "refusal":
            raise LLMRefusal(model, usage_out)


def _bedrock_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Anthropic-style messages (content = str | [{"type": "text", "text": ...}]) -> Converse format."""
    out: list[dict[str, Any]] = []
    for m in messages:
        content = m["content"]
        if isinstance(content, str):
            blocks = [{"text": content}]
        else:
            blocks = [{"text": b["text"]} for b in content if b.get("type") == "text" and b.get("text")]
        out.append({"role": m["role"], "content": blocks})
    return out


_TOOL = "respond"


class BedrockLLM:
    """Amazon Nova through the Bedrock Converse API (D61).

    - auth = the pod's AWS credentials (instance role); no API key
    - JSON output: a forced tool call whose input schema is the requested schema
    - stopReason: max_tokens -> LLMTruncated; content_filtered / guardrail_intervened -> LLMRefusal
    - boto3 is synchronous, so calls run in a worker thread (asyncio.to_thread)
    """

    def __init__(self, region: str) -> None:
        import boto3
        import botocore.config
        import botocore.exceptions

        self._botocore = botocore
        self._errors = botocore.exceptions
        cfg = botocore.config.Config(retries={"max_attempts": 3, "mode": "standard"}, read_timeout=120,
                                     connect_timeout=10)
        self.client = boto3.client("bedrock-runtime", region_name=region, config=cfg)

    @staticmethod
    def _params(task: Task, model: str, system: str, messages: list[dict[str, Any]], max_tokens: int,
                output_schema: dict[str, Any] | None) -> dict[str, Any]:
        params: dict[str, Any] = {
            "modelId": model,
            "system": [{"text": system}],
            "messages": _bedrock_messages(messages),
            # Low temperature: docs/summaries should be factual and repeatable.
            "inferenceConfig": {"maxTokens": max_tokens, "temperature": 0.3 if task == "chat" else 0.2},
        }
        if output_schema is not None:
            params["toolConfig"] = {
                "tools": [{"toolSpec": {"name": _TOOL, "description": "Return the answer in this exact structure.",
                                        "inputSchema": {"json": output_schema}}}],
                "toolChoice": {"tool": {"name": _TOOL}},
            }
        return params

    def _map_error(self, exc: Exception) -> Exception:
        e = self._errors
        if isinstance(exc, e.ClientError):
            code = exc.response.get("Error", {}).get("Code", "")
            msg = str(exc.response.get("Error", {}).get("Message", ""))[:200]
            if code in ("ThrottlingException", "ServiceQuotaExceededException"):
                return RetryableError("LLM rate limited", delay_s=30)
            if code in ("AccessDeniedException", "UnrecognizedClientException", "ExpiredTokenException"):
                return NonRetryableError("AI provider (Bedrock) denied access.", code="ai_auth")
            if code in ("ValidationException", "ResourceNotFoundException"):
                return NonRetryableError(f"AI request was invalid: {msg}", code="ai_bad_request")
            if code in ("ModelTimeoutException", "ServiceUnavailableException", "InternalServerException",
                        "ModelNotReadyException", "ModelErrorException"):
                return RetryableError(f"LLM {code}")
            return NonRetryableError(f"AI error {code}", code="ai_error")
        if isinstance(exc, (e.EndpointConnectionError, e.ConnectTimeoutError, e.ReadTimeoutError)):
            return RetryableError("LLM connection error")
        return exc

    @staticmethod
    def _usage(raw: dict[str, Any] | None) -> Usage:
        raw = raw or {}
        return Usage(int(raw.get("inputTokens", 0)), int(raw.get("outputTokens", 0)),
                     int(raw.get("cacheReadInputTokens", 0)), int(raw.get("cacheWriteInputTokens", 0)))

    async def complete(self, *, task: Task, model: str, system: str, messages: list[dict[str, Any]],
                       max_tokens: int, output_schema: dict[str, Any] | None = None) -> LLMResult:
        import asyncio

        params = self._params(task, model, system, messages, max_tokens, output_schema)
        try:
            resp = await asyncio.to_thread(self.client.converse, **params)
        except Exception as exc:  # mapped to our typed errors below
            mapped = self._map_error(exc)
            if mapped is exc:
                raise
            raise mapped from exc
        usage = self._usage(resp.get("usage"))
        stop = resp.get("stopReason", "end_turn")
        if stop in ("content_filtered", "guardrail_intervened"):
            raise LLMRefusal(model, usage)
        if stop == "max_tokens":
            raise LLMTruncated(model, usage)
        blocks = resp.get("output", {}).get("message", {}).get("content", [])
        text = "".join(b.get("text", "") for b in blocks)
        data = None
        if output_schema is not None:
            tool = next((b["toolUse"] for b in blocks if "toolUse" in b and b["toolUse"].get("name") == _TOOL), None)
            if tool is not None and isinstance(tool.get("input"), dict):
                data = tool["input"]
            else:
                try:
                    data = json.loads(text)
                except json.JSONDecodeError as exc:
                    raise RetryableError("LLM returned invalid JSON") from exc
            text = json.dumps(data)
        return LLMResult(text=text, data=data, stop_reason=stop, model=model, usage=usage)

    async def stream(self, *, task: Task, model: str, system: str, messages: list[dict[str, Any]],
                     max_tokens: int, usage_out: Usage) -> AsyncIterator[str]:
        import asyncio

        params = self._params(task, model, system, messages, max_tokens, None)
        stop_reason = None
        try:
            resp = await asyncio.to_thread(self.client.converse_stream, **params)
            events = iter(resp["stream"])
            while True:
                event = await asyncio.to_thread(next, events, None)
                if event is None:
                    break
                if "contentBlockDelta" in event:
                    piece = event["contentBlockDelta"].get("delta", {}).get("text")
                    if piece:
                        yield piece
                elif "messageStop" in event:
                    stop_reason = event["messageStop"].get("stopReason")
                elif "metadata" in event:
                    u = self._usage(event["metadata"].get("usage"))
                    usage_out.input_tokens, usage_out.output_tokens = u.input_tokens, u.output_tokens
                    usage_out.cache_read_tokens = u.cache_read_tokens
                    usage_out.cache_write_tokens = u.cache_write_tokens
        except Exception as exc:  # mapped to our typed errors below
            mapped = self._map_error(exc)
            if mapped is exc:
                raise
            raise mapped from exc
        if stop_reason in ("content_filtered", "guardrail_intervened"):
            raise LLMRefusal(model, usage_out)


_llm: LLM | None = None


def get_llm() -> LLM:
    global _llm
    if _llm is None:
        s = get_settings()
        if s.ai_mode == "real" and s.ai_provider == "bedrock":
            _llm = BedrockLLM(s.bedrock_region)
        elif s.ai_mode == "real":
            _llm = AnthropicLLM(s.anthropic_api_key.get_secret_value())
        else:
            from docify.ai.fakes import FakeLLM

            _llm = FakeLLM()
    return _llm


def set_llm(llm: LLM | None) -> None:
    global _llm
    _llm = llm
