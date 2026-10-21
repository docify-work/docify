"""Local-only webhook entry (ENV=local): smee.io → here → same normalise() as the Lambda → SQS."""

from __future__ import annotations

import json

from fastapi import APIRouter, Request, Response

from docify.api.errors import Problem
from docify.config import get_settings
from docify.ingest.normalise import MAX_MESSAGE_BYTES, normalise
from docify.ingest.verify import verify_signature
from docify.jobs.queue import get_queue

router = APIRouter(prefix="/dev", tags=["dev"])


@router.post("/webhook", status_code=202, include_in_schema=False)
async def dev_webhook(request: Request) -> Response:
    s = get_settings()
    if not s.is_local:
        raise Problem(404, "Not found", "Not found.", code="not_found")
    body = await request.body()
    secret = s.github_webhook_secret.get_secret_value()
    if secret and not verify_signature(secret, body, request.headers.get("x-hub-signature-256")):
        return Response(status_code=401)
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return Response(status_code=400)
    msg = normalise(request.headers.get("x-github-event", ""), request.headers.get("x-github-delivery", ""), payload)
    if msg is None:
        return Response(status_code=204)
    raw = json.dumps(msg, separators=(",", ":"))
    if len(raw.encode()) > MAX_MESSAGE_BYTES:
        return Response(status_code=413)
    await get_queue().send(msg)
    return Response(status_code=202)
