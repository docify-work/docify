"""Lambda webhook-ingest tests (no AWS: boto3 clients are stubbed)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import importlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1] / "webhook_ingest"
SECRET = "whsec-test"


class FakeSQS:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    def send_message(self, **kw: Any) -> None:
        self.sent.append(kw)


class FakeSSM:
    def get_parameter(self, **kw: Any) -> dict[str, Any]:
        return {"Parameter": {"Value": SECRET}}


@pytest.fixture
def handler(monkeypatch: pytest.MonkeyPatch) -> Any:
    import boto3

    monkeypatch.syspath_prepend(str(ROOT))
    monkeypatch.setenv("QUEUE_URL", "https://sqs.example/q")
    monkeypatch.setenv("WEBHOOK_SECRET_PARAM", "/docify/test/github/webhook_secret")
    monkeypatch.setenv("ENV", "test")
    sqs = FakeSQS()
    monkeypatch.setattr(boto3, "client", lambda name, **_: sqs if name == "sqs" else FakeSSM())
    sys.modules.pop("handler", None)
    mod = importlib.import_module("handler")
    mod.sqs_fake = sqs
    return mod


def event(gh_event: str, payload: dict[str, Any], *, secret: str = SECRET, b64: bool = False) -> dict[str, Any]:
    body = json.dumps(payload).encode()
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return {"requestContext": {"http": {"method": "POST"}},
            "headers": {"X-GitHub-Event": gh_event, "X-GitHub-Delivery": "d-1", "X-Hub-Signature-256": sig},
            "body": base64.b64encode(body).decode() if b64 else body.decode(), "isBase64Encoded": b64}


PUSH = {"ref": "refs/heads/main", "repository": {"id": 1, "default_branch": "main"}, "installation": {"id": 2},
        "before": "a", "after": "b"}


def test_push_is_queued(handler: Any) -> None:
    r = handler.handler(event("push", PUSH), None)
    assert r["statusCode"] == 202
    msg = json.loads(handler.sqs_fake.sent[0]["MessageBody"])
    assert msg["kind"] == "github_event"
    assert msg["after"] == "b"


def test_base64_body(handler: Any) -> None:
    assert handler.handler(event("push", PUSH, b64=True), None)["statusCode"] == 202


def test_bad_signature_rejected_before_anything(handler: Any) -> None:
    r = handler.handler(event("push", PUSH, secret="wrong"), None)
    assert r["statusCode"] == 401
    assert handler.sqs_fake.sent == []


def test_ignored_events_204(handler: Any) -> None:
    r = handler.handler(event("push", {**PUSH, "ref": "refs/heads/feature"}), None)
    assert r["statusCode"] == 204
    assert handler.handler(event("star", {"action": "created"}), None)["statusCode"] == 204


def test_ping(handler: Any) -> None:
    assert handler.handler(event("ping", {"zen": "hi"}), None)["statusCode"] == 200


def test_shared_code_matches_backend() -> None:
    backend = Path(__file__).resolve().parents[2] / "backend" / "src" / "docify" / "ingest"
    for name in ("verify.py", "normalise.py"):
        assert (ROOT / name).read_bytes() == (backend / name).read_bytes(), f"{name} out of sync: make sync-lambda"
