"""GitHub webhook → SQS (Master Doc §5.4, D05).

Runs as a Lambda Function URL so pushes are captured even while the server sleeps.
Order matters: verify the HMAC signature *first* (cheap rejection of junk), then
filter, then enqueue a small message. 202 = queued, 204 = ignored, 401 = bad signature.

`verify.py` and `normalise.py` are copies of `backend/src/docify/ingest/*` (CI checks they match).
"""

from __future__ import annotations

import base64
import json
import os
from typing import Any

import boto3

from normalise import MAX_MESSAGE_BYTES, normalise
from verify import verify_signature

_sqs = boto3.client("sqs")
_ssm = boto3.client("ssm")
_secret: str | None = None  # cached per container


def _webhook_secret() -> str:
    global _secret
    if _secret is None:
        resp = _ssm.get_parameter(Name=os.environ["WEBHOOK_SECRET_PARAM"], WithDecryption=True)
        _secret = resp["Parameter"]["Value"]
    return _secret


def _response(status: int, message: str = "") -> dict[str, Any]:
    return {"statusCode": status, "headers": {"content-type": "text/plain"}, "body": message}


def _log(**fields: Any) -> None:
    # Only ids and outcomes; never payloads or headers (§5.4 logs rule).
    print(json.dumps({"env": os.environ.get("ENV"), **fields}))


def handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    if (event.get("requestContext", {}).get("http", {}).get("method") or "POST") != "POST":
        return _response(405)
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    raw = event.get("body") or ""
    body = base64.b64decode(raw) if event.get("isBase64Encoded") else raw.encode()
    delivery = headers.get("x-github-delivery", "")
    gh_event = headers.get("x-github-event", "")

    if not verify_signature(_webhook_secret(), body, headers.get("x-hub-signature-256")):
        _log(delivery=delivery, event=gh_event, result="bad_signature")
        return _response(401, "invalid signature")
    if gh_event == "ping":
        _log(delivery=delivery, event=gh_event, result="pong")
        return _response(200, "pong")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return _response(400, "invalid json")

    msg = normalise(gh_event, delivery, payload)
    if msg is None:
        _log(delivery=delivery, event=gh_event, action=payload.get("action"), result="ignored")
        return _response(204)
    data = json.dumps(msg, separators=(",", ":"))
    if len(data.encode()) > MAX_MESSAGE_BYTES:
        _log(delivery=delivery, event=gh_event, result="too_large")
        return _response(413, "message too large")  # reconciler will catch up
    _sqs.send_message(QueueUrl=os.environ["QUEUE_URL"], MessageBody=data)
    _log(delivery=delivery, event=gh_event, action=payload.get("action"), result="queued")
    return _response(202, "queued")
