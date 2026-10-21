"""Test setup.

Unit tests need nothing. Integration tests (marked `integration`) need the compose
services: `docker compose up -d postgres valkey elasticmq` (CI uses service containers).
"""

from __future__ import annotations

import os

# Must be set before docify modules read settings.
os.environ.setdefault("ENV", "test")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://docify:docify@localhost:55432/docify_test")
os.environ.setdefault("VALKEY_URL", "redis://localhost:56379/1")
os.environ.setdefault("AWS_ENDPOINT_URL_SQS", "http://localhost:9324")
os.environ.setdefault("SQS_QUEUE_URL", "http://localhost:9324/000000000000/docify-test-events")
os.environ.setdefault("SQS_DLQ_URL", "http://localhost:9324/000000000000/docify-test-events-dlq")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
os.environ.setdefault("AWS_DEFAULT_REGION", "ap-south-1")
os.environ.setdefault("AI_MODE", "fake")
os.environ.setdefault("EMAIL_BACKEND", "console")
os.environ.setdefault("LOG_JSON", "false")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("PUBLIC_BASE_URL", "http://testserver")
os.environ.setdefault("SESSION_PEPPER", "test-pepper-0123456789abcdef0123456789abcdef")
os.environ.setdefault("LOCAL_STORAGE_DIR", ".local-data/test-storage")

import pytest

from tests.helpers.github import RSA_PRIVATE_PEM

os.environ.setdefault("GITHUB_APP_ID", "12345")
os.environ.setdefault("GITHUB_APP_SLUG", "docify-test")
os.environ.setdefault("GITHUB_CLIENT_ID", "Iv1.test")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "gh-client-secret")
os.environ.setdefault("GITHUB_APP_PRIVATE_KEY", RSA_PRIVATE_PEM)
os.environ.setdefault("GOOGLE_CLIENT_ID", "google-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "google-client-secret")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for item in items:
        if "/integration/" in str(item.fspath).replace("\\", "/"):
            item.add_marker(pytest.mark.integration)
