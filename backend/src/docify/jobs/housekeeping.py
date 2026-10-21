"""Daily purge of old rows (Master Doc §6, CronJob `housekeeping` 03:00 Asia/Kolkata)."""

from __future__ import annotations

from sqlalchemy import text

from docify.db.session import session_scope
from docify.observability.logging import get_logger

log = get_logger("docify.housekeeping")

STATEMENTS = {
    "webhook_deliveries": "DELETE FROM webhook_deliveries WHERE received_at < now() - interval '30 days'",
    "jobs_succeeded": "DELETE FROM jobs WHERE status = 'succeeded' AND created_at < now() - interval '90 days'",
    "jobs_failed": "DELETE FROM jobs WHERE status IN ('failed', 'dead') AND created_at < now() - interval '180 days'",
    "sessions": "DELETE FROM sessions WHERE expires_at < now() OR absolute_expires_at < now()",
    "email_tokens": "DELETE FROM email_tokens WHERE expires_at < now() - interval '1 day'",
    "oauth_states": "DELETE FROM oauth_states WHERE expires_at < now()",
    "anon_chat": "DELETE FROM chat_threads WHERE user_id IS NULL AND created_at < now() - interval '24 hours'",
    "invites": "DELETE FROM invites WHERE accepted_at IS NULL AND expires_at < now() - interval '30 days'",
}


async def housekeeping() -> dict[str, int]:
    counts: dict[str, int] = {}
    async with session_scope() as db:
        for name, sql in STATEMENTS.items():
            result = await db.execute(text(sql))
            counts[name] = int(getattr(result, "rowcount", 0) or 0)
    log.info("housekeeping.done", **counts)
    return counts
