"""Chunking + search text (Master Doc §11.2).

- Code: ~60-line windows with 10-line overlap, snapping the start to a nearby
  top-level definition so chunks tend to begin at a function/class.
- Markdown/text: split by headings, ≤ ~800 tokens (~3200 chars).
- `content_hash` = sha256(content) only (no path / line numbers), so a chunk that
  merely moved keeps its hash and its embedding is reused.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import PurePosixPath

CODE_LINES = 60
OVERLAP = 10
SNAP_WINDOW = 15
MD_MAX_CHARS = 3200

_BOUNDARY = re.compile(r"^(?:export\s+)?(?:async\s+)?(?:def|class|function|func|public|private|protected|interface|"
                       r"type|struct|impl|fn|module|resource|@app\.|@router\.)\b")
_HEADING = re.compile(r"^#{1,6}\s")
_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")


@dataclass
class ChunkPiece:
    start_line: int  # 1-based, inclusive
    end_line: int
    content: str

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.content.encode()).hexdigest()


def split_identifiers(text: str) -> str:
    """`getUserById` → `getUserById get user by id`; `snake_case` → `snake_case snake case`."""
    extra: list[str] = []
    for ident in set(_IDENT.findall(text)):
        words = [w for part in ident.split("_") for w in _CAMEL.split(part) if w]
        if len(words) > 1:
            extra.append(" ".join(w.lower() for w in words))
    return text + ("\n" + "\n".join(sorted(extra)) if extra else "")


def path_tokens(path: str) -> str:
    p = PurePosixPath(path)
    words = re.split(r"[/._-]+", str(p))
    return " ".join(w for w in words if w)


def search_text(path: str, content: str) -> str:
    return split_identifiers(content) + "\n" + path_tokens(path)


def chunk_code(text: str) -> list[ChunkPiece]:
    lines = text.splitlines()
    n = len(lines)
    if n == 0:
        return []
    if n <= CODE_LINES:
        return [ChunkPiece(1, n, "\n".join(lines))]
    pieces: list[ChunkPiece] = []
    start = 0
    while start < n:
        end = min(start + CODE_LINES, n)
        if end < n:
            # Prefer to end right before a boundary line near the end of the window.
            for j in range(end, max(start + CODE_LINES - SNAP_WINDOW, start + 1), -1):
                if _BOUNDARY.match(lines[j]):
                    end = j
                    break
        pieces.append(ChunkPiece(start + 1, end, "\n".join(lines[start:end])))
        if end >= n:
            break
        start = max(end - OVERLAP, start + 1)
    return pieces


def chunk_markdown(text: str) -> list[ChunkPiece]:
    lines = text.splitlines()
    sections: list[tuple[int, int]] = []
    start = 0
    for i, line in enumerate(lines):
        if i > start and _HEADING.match(line):
            sections.append((start, i))
            start = i
    if lines:
        sections.append((start, len(lines)))
    pieces: list[ChunkPiece] = []
    for s, e in sections:
        # Split oversized sections by size.
        cur, size = s, 0
        for i in range(s, e):
            size += len(lines[i]) + 1
            if size > MD_MAX_CHARS and i > cur:
                pieces.append(ChunkPiece(cur + 1, i, "\n".join(lines[cur:i])))
                cur, size = i, len(lines[i]) + 1
        if cur < e:
            content = "\n".join(lines[cur:e])
            if content.strip():
                pieces.append(ChunkPiece(cur + 1, e, content))
    return pieces


def chunk_file(path: str, text: str) -> list[ChunkPiece]:
    if PurePosixPath(path).suffix.lower() in (".md", ".rst", ".txt"):
        return chunk_markdown(text)
    return chunk_code(text)


def embed_text(path: str, content: str) -> str:
    return f"{path}\n{content}"
