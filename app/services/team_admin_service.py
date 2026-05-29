from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.exceptions.gateway import NotFoundError, ValidationError
from app.models.llm_model import LLMModel
from app.models.organization import Organization
from app.models.provider import Provider
from app.models.team import Team, TeamAllowedModel, TeamPolicy, TeamProviderPermission
from app.schemas.admin import (
    AllowedModelResponse,
    ProviderPermissionResponse,
    TeamCreateRequest,
    TeamPolicyUpdateRequest,
)


class TeamAdminService:
    def __init__(self, db: Session):
        self._db = db

    def list_teams(self) -> list[Team]:
        return list(self._db.scalars(select(Team).order_by(Team.name)).all())

    def get_team(self, team_id: uuid.UUID) -> Team:
        team = self._db.get(Team, team_id)
        if team is None:
            raise NotFoundError(f"Team not found: {team_id}")
        return team

    def create_team(self, body: TeamCreateRequest) -> Team:
        org = self._db.get(Organization, body.organization_id)
        if org is None:
            raise ValidationError("Organization not found.")

        existing = self._db.scalars(
            select(Team).where(
                Team.organization_id == body.organization_id,
                Team.slug == body.slug,
            )
        ).first()
        if existing is not None:
            raise ValidationError(f"Team slug already exists: {body.slug}")

        team = Team(
            organization_id=body.organization_id,
            name=body.name,
            slug=body.slug,
            is_active=body.is_active,
        )
        self._db.add(team)
        self._db.flush()

        policy = TeamPolicy(team_id=team.id, is_active=True)
        self._db.add(policy)
        self._db.flush()
        self._db.refresh(team)
        return team

    def list_provider_permissions(
        self,
        team_id: uuid.UUID,
    ) -> list[ProviderPermissionResponse]:
        self.get_team(team_id)
        rows = self._db.scalars(
            select(TeamProviderPermission)
            .options(joinedload(TeamProviderPermission.provider))
            .where(TeamProviderPermission.team_id == team_id)
        ).all()
        return [
            ProviderPermissionResponse(
                provider_id=row.provider_id,
                provider_name=row.provider.name,
                provider_type=row.provider.provider_type.value,
                is_allowed=row.is_allowed,
            )
            for row in rows
        ]

    def set_provider_permission(
        self,
        team_id: uuid.UUID,
        *,
        provider_id: uuid.UUID,
        is_allowed: bool,
    ) -> ProviderPermissionResponse:
        self.get_team(team_id)
        provider = self._db.get(Provider, provider_id)
        if provider is None:
            raise NotFoundError(f"Provider not found: {provider_id}")

        row = self._db.scalars(
            select(TeamProviderPermission).where(
                TeamProviderPermission.team_id == team_id,
                TeamProviderPermission.provider_id == provider_id,
            )
        ).first()
        if row is None:
            row = TeamProviderPermission(
                team_id=team_id,
                provider_id=provider_id,
                is_allowed=is_allowed,
            )
            self._db.add(row)
        else:
            row.is_allowed = is_allowed
            self._db.add(row)

        self._db.flush()
        return ProviderPermissionResponse(
            provider_id=provider.id,
            provider_name=provider.name,
            provider_type=provider.provider_type.value,
            is_allowed=is_allowed,
        )

    def list_allowed_models(self, team_id: uuid.UUID) -> list[AllowedModelResponse]:
        self.get_team(team_id)
        rows = self._db.scalars(
            select(TeamAllowedModel)
            .options(
                joinedload(TeamAllowedModel.model).joinedload(LLMModel.provider),
            )
            .where(TeamAllowedModel.team_id == team_id)
        ).all()
        return [
            AllowedModelResponse(
                model_id=row.model_id,
                model_name=row.model.name,
                provider_type=row.model.provider.provider_type.value,
            )
            for row in rows
        ]

    def set_allowed_models(
        self,
        team_id: uuid.UUID,
        model_ids: list[uuid.UUID],
    ) -> list[AllowedModelResponse]:
        self.get_team(team_id)
        existing = self._db.scalars(
            select(TeamAllowedModel).where(TeamAllowedModel.team_id == team_id)
        ).all()
        for row in existing:
            self._db.delete(row)
        self._db.flush()

        for model_id in model_ids:
            model = self._db.get(LLMModel, model_id)
            if model is None:
                raise NotFoundError(f"Model not found: {model_id}")
            self._db.add(TeamAllowedModel(team_id=team_id, model_id=model_id))

        self._db.flush()
        return self.list_allowed_models(team_id)

    def get_policy(self, team_id: uuid.UUID) -> TeamPolicy:
        self.get_team(team_id)
        policy = self._db.scalars(
            select(TeamPolicy).where(TeamPolicy.team_id == team_id)
        ).first()
        if policy is None:
            policy = TeamPolicy(team_id=team_id, is_active=True)
            self._db.add(policy)
            self._db.flush()
            self._db.refresh(policy)
        return policy

    def update_policy(
        self,
        team_id: uuid.UUID,
        body: TeamPolicyUpdateRequest,
    ) -> TeamPolicy:
        policy = self.get_policy(team_id)
        data = body.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(policy, key, value)
        self._db.add(policy)
        self._db.flush()
        self._db.refresh(policy)
        return policy
