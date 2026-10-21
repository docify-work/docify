"""GitHub webhook signature check (X-Hub-Signature-256).

Pure standard library: this file is copied verbatim into the Lambda
(`make sync-lambda`; CI fails if the copies differ).
"""

from __future__ import annotations

import hashlib
import hmac


def verify_signature(secret: str, body: bytes, signature_header: str | None) -> bool:
    """HMAC-SHA256 over the *raw* request body, compared in constant time."""
    if not secret or not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)
