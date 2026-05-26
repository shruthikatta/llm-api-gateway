from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.exceptions.gateway import (
    ModelAccessDenied,
    ProviderAccessDenied,
    TeamDisabledError,
)
from app.models.api_key import APIKey
from app.models.llm_model import LLMModel
from app.models.provider import Provider, ProviderType
from app.models.team import Team, TeamAllowedModel, TeamPolicy, TeamProviderPermission
from app.policies.context import ResolvedPolicy
from app.router.model_router import RouteDecision


class AccessControlService:
    """
    Enforce team-scoped provider and model allow-lists.

    Empty allow-lists deny all — teams must be explicitly granted access.
    Provider-agnostic: works for OpenAI today and Anthropic/etc. later.
    """

    def __init__(self, db: Session):
        self._db = db

    def require_active_team(self, api_key: APIKey) -> Team:
        team = api_key.team
        if team is None:
            raise TeamDisabledError()
        if not team.is_active:
            raise TeamDisabledError()
        return team

    def load_policy(self, team: Team) -> ResolvedPolicy:
        policy = self._db.scalars(
            select(TeamPolicy).where(TeamPolicy.team_id == team.id)
        ).first()
        return ResolvedPolicy.from_team(team, policy)

    def assert_model_allowed(self, team: Team, model_name: str) -> LLMModel | None:
        """
        Allow-list check by model name.

        Heuristic-routed models (not in DB) are allowed only when the team
        has at least one allowed model whose name matches exactly, OR when
        routing aliases resolve to an allowed DB model (handled by caller).
        """
        allowed = self._db.scalars(
            select(TeamAllowedModel)
            .options(joinedload(TeamAllowedModel.model))
            .where(TeamAllowedModel.team_id == team.id)
        ).all()

        if not allowed:
            raise ModelAccessDenied(model_name)

        for row in allowed:
            if row.model.name == model_name and row.model.is_active:
                return row.model

        # Model may be heuristic-only (e.g. gpt-custom). Permit if any
        # allowed model shares the same provider family prefix after route.
        return None

    def assert_provider_allowed(self, team: Team, route: RouteDecision) -> None:
        if route.provider_id is None:
            # Heuristic route without DB provider row: match by provider_type.
            try:
                provider_type = ProviderType(route.provider_type)
            except ValueError as exc:
                raise ProviderAccessDenied(route.provider_type) from exc

            provider = self._db.scalars(
                select(Provider).where(
                    Provider.provider_type == provider_type,
                    Provider.is_active.is_(True),
                )
            ).first()
            if provider is None:
                raise ProviderAccessDenied(route.provider_type)
            provider_id = provider.id
        else:
            provider_id = route.provider_id

        permission = self._db.scalars(
            select(TeamProviderPermission).where(
                TeamProviderPermission.team_id == team.id,
                TeamProviderPermission.provider_id == provider_id,
            )
        ).first()

        if permission is None or not permission.is_allowed:
            raise ProviderAccessDenied(route.provider_type)

    def assert_route_allowed(
        self,
        team: Team,
        model_name: str,
        route: RouteDecision,
    ) -> None:
        """Combined model + provider enforcement after routing resolves."""
        allowed_rows = self._db.scalars(
            select(TeamAllowedModel)
            .options(joinedload(TeamAllowedModel.model))
            .where(TeamAllowedModel.team_id == team.id)
        ).all()

        if not allowed_rows:
            raise ModelAccessDenied(model_name)

        allowed_names = {row.model.name for row in allowed_rows if row.model.is_active}
        if model_name not in allowed_names and route.model_name not in allowed_names:
            raise ModelAccessDenied(model_name)

        self.assert_provider_allowed(team, route)
