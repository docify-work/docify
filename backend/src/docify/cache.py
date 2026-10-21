"""Valkey (Redis-compatible) client + sliding-window rate limiter.

Valkey is a non-authoritative cache: losing it only resets rate limits and cached
GitHub installation tokens (Master Doc D04).
"""

from __future__ import annotations

import time
import uuid

import redis.asyncio as redis

from docify.config import get_settings

_client: redis.Redis | None = None


def get_valkey() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(get_settings().valkey_url, decode_responses=True, socket_timeout=2)
    return _client


async def close_valkey() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
    _client = None


class RateLimited(Exception):
    def __init__(self, retry_after: int) -> None:
        super().__init__(f"rate limited, retry after {retry_after}s")
        self.retry_after = retry_after


async def hit(key: str, *, limit: int, window_s: int, client: redis.Redis | None = None) -> None:
    """Sliding-window limiter on a sorted set. Raises RateLimited when over the limit.

    If Valkey is unreachable we fail *open* for availability — except callers that
    protect money (AI) also have DB-backed budgets, so the risk is bounded.
    """
    r = client or get_valkey()
    now = time.time()
    full = f"rl:{key}"
    try:
        async with r.pipeline(transaction=True) as pipe:
            pipe.zremrangebyscore(full, 0, now - window_s)
            pipe.zadd(full, {f"{now}:{uuid.uuid4().hex[:8]}": now})
            pipe.zcard(full)
            pipe.zrange(full, 0, 0, withscores=True)
            pipe.expire(full, window_s)
            _, _, count, oldest, _ = await pipe.execute()
    except (redis.ConnectionError, redis.TimeoutError):
        return
    if count > limit:
        oldest_ts = oldest[0][1] if oldest else now
        raise RateLimited(max(1, int(oldest_ts + window_s - now) + 1))


async def daily_counter(key: str, *, limit: int, client: redis.Redis | None = None) -> None:
    """Fixed daily window (UTC day) used for chat/search quotas."""
    r = client or get_valkey()
    day = time.strftime("%Y%m%d", time.gmtime())
    full = f"day:{day}:{key}"
    try:
        count = await r.incr(full)
        if count == 1:
            await r.expire(full, 2 * 86400)
    except (redis.ConnectionError, redis.TimeoutError):
        return
    if count > limit:
        tomorrow = (int(time.time()) // 86400 + 1) * 86400
        raise RateLimited(tomorrow - int(time.time()))
