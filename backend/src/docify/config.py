"""Runtime configuration (12-factor): everything comes from environment variables.

See Master Doc §15.1 for the full list. Secrets arrive as env vars too (from the
`docify-app` / `docify-db` Kubernetes Secrets created by External Secrets).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: Literal["local", "test", "staging", "prod"] = "local"
    version: str = Field(default="dev", alias="APP_VERSION")
    public_base_url: str = "http://localhost:5173"
    log_level: str = "INFO"
    log_json: bool = True

    # --- data ---
    database_url: str = "postgresql+asyncpg://docify:docify@localhost:55432/docify"
    db_pool_size: int = 5
    valkey_url: str = "redis://localhost:56379/0"

    # --- AWS ---
    aws_region: str = "ap-south-1"
    sqs_queue_url: str = "http://localhost:9324/000000000000/docify-local-events"
    sqs_dlq_url: str = "http://localhost:9324/000000000000/docify-local-events-dlq"
    aws_endpoint_url_sqs: str | None = None
    storage_backend: Literal["local", "s3"] = "local"
    s3_repo_cache_bucket: str = ""
    local_storage_dir: str = ".local-data/storage"

    # --- email ---
    email_backend: Literal["smtp", "ses", "console"] = "smtp"
    email_from: str = "Docify <no-reply@docify.work>"
    smtp_host: str = "localhost"
    smtp_port: int = 1025

    # --- security ---
    session_pepper: SecretStr = SecretStr("local-dev-pepper-change-me-0123456789abcdef")
    origin_verify_header: SecretStr | None = None
    session_days: int = 14
    session_absolute_days: int = 60

    # --- GitHub App ---
    github_app_id: str = ""
    github_app_slug: str = ""
    github_client_id: str = ""
    github_client_secret: SecretStr = SecretStr("")
    github_app_private_key: SecretStr = SecretStr("")
    github_webhook_secret: SecretStr = SecretStr("")
    github_api_url: str = "https://api.github.com"
    github_web_url: str = "https://github.com"

    # --- Google ---
    google_client_id: str = ""
    google_client_secret: SecretStr = SecretStr("")

    # --- AI ---
    ai_mode: Literal["fake", "real"] = "fake"
    anthropic_api_key: SecretStr = SecretStr("")
    voyage_api_key: SecretStr = SecretStr("")
    # Owner decision (Q4, 2026-10-21): Haiku for everything for now.
    llm_model_summary: str = "claude-haiku-5-5"
    llm_model_doc: str = "claude-haiku-5-5"
    llm_model_chat: str = "claude-haiku-5-5"
    embed_model: str = "voyage-code-3"
    embed_dim: int = 1024
    ai_daily_budget_usd: float = 2.0
    ai_ws_monthly_budget_usd: float = 3.0
    chat_user_daily_limit: int = 30
    chat_anon_ip_daily_limit: int = 5
    chat_anon_global_daily_limit: int = 100
    search_anon_ip_daily_limit: int = 30
    rag_min_sim: float = 0.45

    # --- limits ---
    repo_max_files: int = 3000
    repo_max_mb: int = 100
    ws_max_repos: int = 5
    file_max_kb: int = 200

    demo_workspace_slug: str = "demo"
    worker_concurrency: int = 2
    worker_heartbeat_file: str = "/tmp/worker-heartbeat"  # noqa: S108 - emptyDir in k8s
    metrics_port: int = 9000

    @field_validator("database_url")
    @classmethod
    def _async_driver(cls, v: str) -> str:
        # Accept plain postgres URLs and force the asyncpg driver.
        if v.startswith("postgres://"):
            v = "postgresql://" + v.removeprefix("postgres://")
        if v.startswith("postgresql://"):
            v = "postgresql+asyncpg://" + v.removeprefix("postgresql://")
        return v

    @property
    def is_local(self) -> bool:
        return self.env in ("local", "test")

    @property
    def cookie_secure(self) -> bool:
        return not self.is_local

    @property
    def github_configured(self) -> bool:
        return bool(self.github_app_id and self.github_client_id)

    @property
    def google_configured(self) -> bool:
        return bool(self.google_client_id)


@lru_cache
def get_settings() -> Settings:
    return Settings()
