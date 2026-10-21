"""Secret redaction before anything is stored or sent to an LLM (Master Doc §9.5)."""

from __future__ import annotations

import re

REDACTED = "[REDACTED]"

_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----", re.S),
    re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{22,}\b"),
    re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\bsk_live_[A-Za-z0-9]{16,}\b"),
    re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
]
# key = "value" style assignments; keep the key so code still reads naturally.
_ASSIGNMENT = re.compile(
    r"""(?i)\b([A-Za-z0-9_]*(?:password|passwd|secret|token|api[_-]?key)[A-Za-z0-9_]*)(\s*[:=]\s*)(['"])([^'"\n]{8,})\3"""
)


def redact(text: str) -> tuple[str, int]:
    """Returns (redacted text, number of replacements)."""
    count = 0
    for pattern in _PATTERNS:
        text, n = pattern.subn(REDACTED, text)
        count += n

    def _assign(m: re.Match[str]) -> str:
        return f"{m.group(1)}{m.group(2)}{m.group(3)}{REDACTED}{m.group(3)}"

    text, n = _ASSIGNMENT.subn(_assign, text)
    return text, count + n
