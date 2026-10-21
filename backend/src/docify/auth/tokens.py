"""Opaque random tokens; only their HMAC is stored (Master Doc §10.1).

A DB leak therefore doesn't leak usable session/email/invite/oauth-state tokens:
the attacker would also need `SESSION_PEPPER`, which lives only in SSM/K8s.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

from docify.config import get_settings


def new_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def token_hmac(token: str) -> bytes:
    pepper = get_settings().session_pepper.get_secret_value().encode()
    return hmac.new(pepper, token.encode(), hashlib.sha256).digest()


def constant_time_equals(a: str | bytes, b: str | bytes) -> bool:
    if isinstance(a, str):
        a = a.encode()
    if isinstance(b, str):
        b = b.encode()
    return hmac.compare_digest(a, b)
