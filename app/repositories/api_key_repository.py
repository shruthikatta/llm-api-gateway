from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.api_key import APIKey
from app.models.user import User


class APIKeyRepository:
    """
    Repository for APIKey database operations.

    Does not commit — the caller / session dependency owns the
    transaction boundary.
    """

    def __init__(self, db: Session):
        self.db = db

    def create(self, api_key: APIKey) -> APIKey:
        self.db.add(api_key)
        self.db.flush()
        self.db.refresh(api_key)
        return api_key

    def get_by_hash(self, key_hash: str) -> APIKey | None:
        return self.db.scalars(
            select(APIKey).where(APIKey.key_hash == key_hash)
        ).first()

    def get_by_hash_with_user(self, key_hash: str) -> APIKey | None:
        return self.db.scalars(
            select(APIKey)
            .options(
                joinedload(APIKey.user).joinedload(User.organization),
                joinedload(APIKey.team),
            )
            .where(APIKey.key_hash == key_hash)
        ).first()

    def touch_last_used(self, api_key: APIKey) -> None:
        api_key.last_used_at = datetime.now(timezone.utc)
        self.db.add(api_key)
        self.db.flush()

    def revoke(self, api_key: APIKey) -> APIKey:
        api_key.is_active = False
        self.db.add(api_key)
        self.db.flush()
        self.db.refresh(api_key)
        return api_key

    def delete(self, api_key: APIKey) -> None:
        self.db.delete(api_key)
        self.db.flush()
