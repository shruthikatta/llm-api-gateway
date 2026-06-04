from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.quota import AuditLog
from app.models.user import User


class AuditService:
    """Append-only audit trail for administrative actions."""

    def __init__(self, db: Session):
        self._db = db

    def record(
        self,
        *,
        actor: User,
        action: str,
        resource_type: str,
        resource_id: str | uuid.UUID,
        details: dict[str, Any] | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            actor_user_id=actor.id,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id),
            details=details or {},
        )
        self._db.add(entry)
        self._db.flush()
        return entry

    def list_recent(self, *, limit: int = 100) -> list[AuditLog]:
        return list(
            self._db.scalars(
                select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
            ).all()
        )
