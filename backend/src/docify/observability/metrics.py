"""Prometheus metrics (Master Doc §16.2). Served on a separate port (9000), never via Ingress."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, start_http_server

HTTP_REQUESTS = Counter("docify_http_requests_total", "HTTP requests", ["route", "method", "status"])
HTTP_DURATION = Histogram(
    "docify_http_request_duration_seconds", "HTTP request duration", ["route", "method"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
JOBS = Counter("docify_jobs_total", "Jobs finished", ["type", "status"])
JOB_DURATION = Histogram(
    "docify_job_duration_seconds", "Job duration", ["type"],
    buckets=(1, 5, 15, 30, 60, 120, 300, 600, 1800),
)
QUEUE_MESSAGES = Gauge("docify_queue_messages", "SQS messages", ["queue", "kind"])
QUEUE_OLDEST_AGE = Gauge("docify_queue_oldest_age_seconds", "Age of the oldest queued job", ["queue"])
LLM_TOKENS = Counter("docify_llm_tokens_total", "LLM tokens", ["model", "kind"])
LLM_COST = Counter("docify_llm_cost_usd_total", "LLM cost in USD", ["model", "purpose"])
AI_BUDGET_REMAINING = Gauge("docify_ai_budget_remaining_usd", "Remaining AI budget", ["scope"])
EMBED_TOKENS = Counter("docify_embeddings_tokens_total", "Embedding tokens", ["model"])
GITHUB_REQUESTS = Counter("docify_github_requests_total", "GitHub API requests", ["status"])
GITHUB_RATELIMIT = Gauge("docify_github_ratelimit_remaining", "GitHub rate limit remaining", ["installation"])
CHAT_REQUESTS = Counter("docify_chat_requests_total", "Chat requests", ["result"])
AUTH_EVENTS = Counter("docify_auth_events_total", "Auth events", ["type", "result"])
WORKER_BUSY = Gauge("docify_worker_busy_slots", "Worker slots in use")


def start_metrics_server(port: int) -> None:
    start_http_server(port)
