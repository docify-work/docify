"""Password hashing (Argon2id via pwdlib) + password rules (Master Doc §10.3)."""

from __future__ import annotations

import asyncio
from functools import lru_cache
from importlib import resources

from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

_hasher = PasswordHash((Argon2Hasher(),))

MIN_LEN, MAX_LEN = 10, 128

# A precomputed hash so login with an unknown email costs the same time as a real check
# (prevents user enumeration by timing).
_DUMMY_HASH = _hasher.hash("docify-dummy-password-for-timing")


class PasswordRuleError(ValueError):
    pass


@lru_cache
def _common_passwords() -> frozenset[str]:
    text = resources.files("docify.auth").joinpath("common_passwords.txt").read_text(encoding="utf-8")
    return frozenset(
        line.strip().lower() for line in text.splitlines() if line.strip() and not line.startswith("#")
    )


def check_password_rules(password: str, *, email: str | None = None) -> None:
    if not MIN_LEN <= len(password) <= MAX_LEN:
        raise PasswordRuleError(f"Password must be {MIN_LEN}-{MAX_LEN} characters long.")
    if password.lower() in _common_passwords():
        raise PasswordRuleError("This password is too common. Please choose another one.")
    if email and password.lower() == email.lower():
        raise PasswordRuleError("Password must not be your email address.")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


async def ahash_password(password: str) -> str:
    """Argon2 is CPU-bound (~tens of ms): run it off the event loop so SSE streams don't stall."""
    return await asyncio.to_thread(_hasher.hash, password)


async def averify_password(password: str, password_hash: str | None) -> bool:
    return await asyncio.to_thread(verify_password, password, password_hash)


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        _hasher.verify(password, _DUMMY_HASH)
        return False
    try:
        return _hasher.verify(password, password_hash)
    except Exception:  # malformed hash
        return False
