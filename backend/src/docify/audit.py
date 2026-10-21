"""Audit trail for security-relevant actions (who did what, when)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from docify.db.models import AuditEvent


def audit(db: AsyncSession, action: str, *, actor: uuid.UUID | None = None, workspace_id: uuid.UUID | None = None,
          target: str | None = None, **meta: Any) -> None:
    db.add(AuditEvent(action=action, actor_user_id=actor, workspace_id=workspace_id, target=target, meta=meta))
