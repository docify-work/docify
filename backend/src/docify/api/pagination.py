"""Keyset (cursor) pagination on (created_at DESC, id DESC)."""

from __future__ import annotations

import base64
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Select, and_, or_

from docify.api.errors import bad_request


def encode(created_at: datetime, row_id: uuid.UUID) -> str:
    return base64.urlsafe_b64encode(f"{created_at.isoformat()}|{row_id}".encode()).decode().rstrip("=")


def decode(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
        ts, rid = raw.split("|", 1)
        return datetime.fromisoformat(ts), uuid.UUID(rid)
    except Exception as exc:
        raise bad_request("Invalid cursor.", code="invalid_cursor") from exc


def apply(stmt: Select[Any], model: Any, cursor: str | None, limit: int) -> Select[Any]:
    if cursor:
        ts, rid = decode(cursor)
        stmt = stmt.where(or_(model.created_at < ts, and_(model.created_at == ts, model.id < rid)))
    return stmt.order_by(model.created_at.desc(), model.id.desc()).limit(limit + 1)


def next_cursor(rows: list[Any], limit: int, get: Any = lambda r: r) -> tuple[list[Any], str | None]:
    if len(rows) <= limit:
        return rows, None
    rows = rows[:limit]
    last = get(rows[-1])
    return rows, encode(last.created_at, last.id)
