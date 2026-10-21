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


class LLMRefusal(Exception):
    """The model declined (stop_reason=refusal). Handled per F19: section skipped, job continues."""


class LLMTruncated(Exception):
    """stop_reason=max_tokens. Caller may retry once with fewer inputs (F19)."""


# USD per million tokens: (input ≤100K prompt, output, input >100K prompt, output >100K prompt).
PRICES: dict[str, tuple[float, float, float, float]] = {
    "claude-haiku-5-5": (0.10, 0.50, 0.50, 2.50),
    "claude-sonnet-5-5": (2.00, 10.00, 2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00, 4.00, 20.00),
}
EMBED_PRICES = {"voyage-code-3": 0.18, "fake-embed": 0.0}


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
            raise LLMRefusal(model)
        text = "".join(b.text for b in resp.content if b.type == "text")
        if resp.stop_reason == "max_tokens":
            raise LLMTruncated(model)
        data = None
        if output_schema is not None:
            try:
                data = json.loads(text)
            except json.JSONDecodeError as exc:
                raise RetryableError("LLM returned invalid JSON") from exc
        return LLMResult(text=text, data=data, stop_reason=resp.stop_reason or "end_turn", model=model, usage=usage)

    async def stream(self, *, task: Task, model: str, system: str, messages: list[dict[str, Any]],
                     max_tokens: int, usage_out: Usage) -> AsyncIterator[str]:
        try:
            async with self.client.messages.stream(**self._params(task, model, system, messages, max_tokens,
                                                                  None)) as stream:
                async for text in stream.text_stream:
                    yield text
                final = await stream.get_final_message()
        except self._anthropic.AnthropicError as exc:
            raise self._map_error(exc) from exc
        u = final.usage
        usage_out.input_tokens = u.input_tokens or 0
        usage_out.output_tokens = u.output_tokens or 0
        usage_out.cache_read_tokens = getattr(u, "cache_read_input_tokens", 0) or 0
        usage_out.cache_write_tokens = getattr(u, "cache_creation_input_tokens", 0) or 0
        if final.stop_reason == "refusal":
            raise LLMRefusal(model)


_llm: LLM | None = None


def get_llm() -> LLM:
    global _llm
    if _llm is None:
        s = get_settings()
        if s.ai_mode == "real":
            _llm = AnthropicLLM(s.anthropic_api_key.get_secret_value())
        else:
            from docify.ai.fakes import FakeLLM

            _llm = FakeLLM()
    return _llm


def set_llm(llm: LLM | None) -> None:
    global _llm
    _llm = llm
