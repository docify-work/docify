from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from docify.api import pagination
from docify.api.errors import Problem
from docify.api.routers.auth import _safe_redirect
from docify.auth.passwords import PasswordRuleError, check_password_rules, hash_password, verify_password
from docify.auth.tokens import new_token, token_hmac


def test_password_rules() -> None:
    check_password_rules("correct horse battery 9")
    for bad in ("short", "x" * 129, "qwertyuiop"):
        with pytest.raises(PasswordRuleError):
            check_password_rules(bad)
    with pytest.raises(PasswordRuleError):
        check_password_rules("me@example.com", email="me@example.com")


def test_hash_roundtrip() -> None:
    h = hash_password("correct horse battery 9")
    assert h.startswith("$argon2id$")
    assert verify_password("correct horse battery 9", h)
    assert not verify_password("wrong", h)
    assert not verify_password("x", None)
    assert not verify_password("x", "not-a-hash")


def test_token_hmac_stable_and_distinct() -> None:
    t = new_token()
    assert len(t) >= 40
    assert token_hmac(t) == token_hmac(t)
    assert token_hmac(t) != token_hmac(new_token())


@pytest.mark.parametrize(("value", "expected"), [
    ("/w/acme", "/w/acme"), (None, "/"), ("https://evil.com", "/"), ("//evil.com", "/"), ("/\\evil", "/"),
])
def test_safe_redirect(value: str | None, expected: str) -> None:
    assert _safe_redirect(value) == expected


def test_cursor_roundtrip() -> None:
    ts, rid = datetime.now(UTC), uuid.uuid4()
    assert pagination.decode(pagination.encode(ts, rid)) == (ts, rid)
    with pytest.raises(Problem):
        pagination.decode("garbage!!")
