from __future__ import annotations

from dataclasses import dataclass
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.config.store import get_config_store
from app.models.llm_model import LLMModel
from app.models.provider import Provider, ProviderType
from app.router.exceptions import (
    ModelInactiveError,
    ModelNotFoundError,
    ProviderInactiveError,
)


@dataclass(slots=True, frozen=True)
class RouteDecision:
    """Resolved routing target for an LLM request."""

    model_id: uuid.UUID | None
    model_name: str
    provider_id: uuid.UUID | None
    provider_name: str
    provider_type: str
    base_url: str | None


class ModelRouter:
    """
    Resolve which provider should handle a given model.

    Prefer database configuration. Fall back to YAML routing heuristics
    for models not yet registered.
    """

    def __init__(self, db: Session):
        self._db = db

    def resolve(self, model_name: str) -> RouteDecision:
        record = self._db.scalars(
            select(LLMModel)
            .options(joinedload(LLMModel.provider))
            .where(LLMModel.name == model_name)
        ).first()

        if record is not None:
            return self._from_record(record)

        return self._heuristic_route(model_name)

    def resolve_for_provider(
        self,
        model_name: str,
        *,
        provider_type: str,
        fallback_model: str | None = None,
    ) -> RouteDecision | None:
        config = get_config_store().get()
        if not config.provider_enabled(provider_type):
            return None

        try:
            enum_type = ProviderType(provider_type)
        except ValueError:
            return None

        provider = self._db.scalars(
            select(Provider).where(
                Provider.provider_type == enum_type,
                Provider.is_active.is_(True),
            )
        ).first()

        resolved_model = fallback_model or model_name
        if provider is None:
            return RouteDecision(
                model_id=None,
                model_name=resolved_model,
                provider_id=None,
                provider_name=provider_type,
                provider_type=provider_type,
                base_url=config.provider_base_url(provider_type),
            )

        return RouteDecision(
            model_id=None,
            model_name=resolved_model,
            provider_id=provider.id,
            provider_name=provider.name,
            provider_type=provider.provider_type.value,
            base_url=provider.base_url,
        )

    def _from_record(self, record: LLMModel) -> RouteDecision:
        if not record.is_active:
            raise ModelInactiveError(record.name)

        provider: Provider = record.provider
        if not provider.is_active:
            raise ProviderInactiveError(provider.provider_type.value)

        return RouteDecision(
            model_id=record.id,
            model_name=record.name,
            provider_id=provider.id,
            provider_name=provider.name,
            provider_type=provider.provider_type.value,
            base_url=provider.base_url,
        )

    def _heuristic_route(self, model_name: str) -> RouteDecision:
        config = get_config_store().get()
        provider_name: str | None = None
        for rule in config.routing.heuristics:
            if model_name.startswith(rule.prefix):
                provider_name = rule.provider
                break

        if provider_name is None:
            raise ModelNotFoundError(model_name)

        try:
            provider_type = ProviderType(provider_name)
        except ValueError as exc:
            raise ModelNotFoundError(model_name) from exc

        provider = self._db.scalars(
            select(Provider).where(
                Provider.provider_type == provider_type,
                Provider.is_active.is_(True),
            )
        ).first()

        return RouteDecision(
            model_id=None,
            model_name=model_name,
            provider_id=provider.id if provider else None,
            provider_name=provider.name if provider else provider_name,
            provider_type=provider_type.value,
            base_url=provider.base_url if provider else None,
        )
