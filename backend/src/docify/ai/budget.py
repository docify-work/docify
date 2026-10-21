"""AI spend tracking + hard caps (Master Doc §11.6).

Every LLM/embedding call is recorded in `llm_usage` with its USD cost, and budgets
are checked *before* calls. Note: each environment has its own database, so the
daily budget applies per environment (set staging lower via AI_DAILY_BUDGET_USD).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from docify.ai.llm import EMBED_PRICES, Usage, cost_usd
from docify.config import get_settings
from docify.db.models import LlmUsage
from docify.jobs.errors import BudgetExceeded
from docify.observability.metrics import AI_BUDGET_REMAINING, EMBED_TOKENS, LLM_COST, LLM_TOKENS


async def spent_today(db: AsyncSession) -> float:
    v = (await db.execute(select(func.coalesce(func.sum(LlmUsage.cost_usd), 0)).where(
        LlmUsage.created_at >= text("date_trunc('day', now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC'")))).scalar_one()
    return float(v)


async def spent_this_month(db: AsyncSession, workspace_id: uuid.UUID) -> float:
    v = (await db.execute(select(func.coalesce(func.sum(LlmUsage.cost_usd), 0)).where(
        LlmUsage.workspace_id == workspace_id,
        LlmUsage.created_at >= text("date_trunc('month', now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC'")))).scalar_one()
    return float(v)


async def check_budget(db: AsyncSession, workspace_id: uuid.UUID | None) -> None:
    s = get_settings()
    today = await spent_today(db)
    AI_BUDGET_REMAINING.labels("daily").set(max(0.0, s.ai_daily_budget_usd - today))
    if today >= s.ai_daily_budget_usd:
        raise BudgetExceeded("daily AI budget reached")
    if workspace_id is not None:
        month = await spent_this_month(db, workspace_id)
        if month >= s.ai_ws_monthly_budget_usd:
            raise BudgetExceeded("workspace monthly AI budget reached")


def record_llm(db: AsyncSession, *, workspace_id: uuid.UUID | None, job_id: uuid.UUID | None, purpose: str,
               model: str, usage: Usage) -> float:
    cost = cost_usd(model, usage)
    db.add(LlmUsage(workspace_id=workspace_id, job_id=job_id, purpose=purpose, provider="anthropic", model=model,
                    input_tokens=usage.input_tokens + usage.cache_write_tokens, output_tokens=usage.output_tokens,
                    cache_read_tokens=usage.cache_read_tokens, cost_usd=Decimal(str(round(cost, 6)))))
    LLM_TOKENS.labels(model, "input").inc(usage.input_tokens)
    LLM_TOKENS.labels(model, "output").inc(usage.output_tokens)
    LLM_TOKENS.labels(model, "cache_read").inc(usage.cache_read_tokens)
    LLM_COST.labels(model, purpose).inc(cost)
    return cost


def record_embedding(db: AsyncSession, *, workspace_id: uuid.UUID | None, job_id: uuid.UUID | None, model: str,
                     tokens: int, purpose: str = "embed") -> float:
    cost = tokens * EMBED_PRICES.get(model, 0.0) / 1_000_000
    db.add(LlmUsage(workspace_id=workspace_id, job_id=job_id, purpose=purpose, provider="voyage", model=model,
                    input_tokens=tokens, cost_usd=Decimal(str(round(cost, 6)))))
    EMBED_TOKENS.labels(model).inc(tokens)
    return cost


@dataclass
class TokenMeter:
    """Per-job input-token cap (§11.6). Docgen stops adding inputs when it runs dry → doc marked partial."""

    limit: int
    used: int = 0

    def can_spend(self, tokens: int) -> bool:
        return self.used + tokens <= self.limit

    def spend(self, tokens: int) -> None:
        self.used += tokens


def estimate_tokens(text_: str) -> int:
    # Rough and conservative (newer tokenizers count ~30% more than chars/4).
    return int(len(text_) / 3.2) + 1
