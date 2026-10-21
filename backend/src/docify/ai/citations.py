"""Citation markers `[[path:start-end]]` → validated, then rendered as GitHub permalinks (§11.3 item 6)."""

from __future__ import annotations

import re
from urllib.parse import quote

CITATION = re.compile(r"\[\[([^\[\]:\n]+):(\d+)(?:-(\d+))?\]\]")


def extract(text: str) -> list[tuple[str, int, int]]:
    out = []
    for m in CITATION.finditer(text):
        a = int(m.group(2))
        b = int(m.group(3) or a)
        out.append((m.group(1).strip(), a, b))
    return out


def validate(text: str, line_counts: dict[str, int]) -> tuple[str, int]:
    """Drop citations whose path doesn't exist or whose lines are out of range. Returns (text, removed)."""
    removed = 0

    def _fix(m: re.Match[str]) -> str:
        nonlocal removed
        path = m.group(1).strip()
        a = int(m.group(2))
        b = int(m.group(3) or a)
        total = line_counts.get(path)
        if total is None or a < 1 or b < a or b > total:
            removed += 1
            return ""
        return f"[[{path}:{a}-{b}]]"

    fixed = CITATION.sub(_fix, text)
    fixed = re.sub(r"[ \t]+([.,;:])", r"\1", fixed)
    return fixed, removed


def permalink(full_name: str, sha: str, path: str, a: int, b: int) -> str:
    anchor = f"#L{a}" if a == b else f"#L{a}-L{b}"
    return f"https://github.com/{full_name}/blob/{sha}/{quote(path)}{anchor}"


def render(text: str, full_name: str, sha: str) -> str:
    """Replace markers with Markdown links for the frontend."""

    def _link(m: re.Match[str]) -> str:
        path = m.group(1).strip()
        a = int(m.group(2))
        b = int(m.group(3) or a)
        label = f"{path}:{a}" if a == b else f"{path}:{a}-{b}"
        return f"[`{label}`]({permalink(full_name, sha, path, a, b)})"

    return CITATION.sub(_link, text)
