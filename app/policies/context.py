from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.models.team import Team, TeamPolicy


@dataclass(slots=True)
class ResolvedPolicy:
    """Normalized team policy snapshot used on the request path."""

    team_id: str
    team_slug: str
    system_prompt: str | None = None
    compliance_prompt: str | None = None
    content_filter: dict[str, Any] = field(default_factory=dict)
    routing: dict[str, Any] = field(default_factory=dict)
    enrichment: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_team(cls, team: Team, policy: TeamPolicy | None) -> ResolvedPolicy:
        if policy is None or not policy.is_active:
            return cls(team_id=str(team.id), team_slug=team.slug)
        return cls(
            team_id=str(team.id),
            team_slug=team.slug,
            system_prompt=policy.system_prompt,
            compliance_prompt=policy.compliance_prompt,
            content_filter=dict(policy.content_filter_config or {}),
            routing=dict(policy.routing_config or {}),
            enrichment=dict(policy.enrichment_config or {}),
        )
