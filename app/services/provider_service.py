from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.provider import Provider
from app.schemas.provider import ProviderOut


class ProviderService:
    def __init__(self, db: Session):
        self._db = db

    def list_providers(self, *, enabled_only: bool = False) -> list[ProviderOut]:
        stmt = select(Provider).order_by(Provider.name)
        if enabled_only:
            stmt = stmt.where(Provider.is_active.is_(True))

        providers = self._db.scalars(stmt).all()
        return [
            ProviderOut(
                id=str(provider.id),
                name=provider.name,
                provider_type=provider.provider_type.value,
                base_url=provider.base_url,
                enabled=provider.is_active,
            )
            for provider in providers
        ]
