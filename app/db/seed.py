from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.auth.security import generate_api_key
from app.models.api_key import APIKey
from app.models.llm_model import LLMModel
from app.models.llm_request import LLMRequest, RequestStatus
from app.models.organization import Organization
from app.models.provider import Provider, ProviderType
from app.models.team import Team, TeamAllowedModel, TeamPolicy, TeamProviderPermission
from app.models.quota import RateLimitPriority, TeamBudget, TeamRateLimit
from app.models.usage_record import UsageRecord
from app.models.user import User, UserRole


def seed(db: Session) -> None:
    """
    Seed a working OpenAI-first environment.

    Other providers may exist in the catalog for future enablement, but the
    default team is granted OpenAI access only.
    """
    try:
        organization = Organization(
            id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
            name="Example Org",
            slug="example-org",
            is_active=True,
        )
        db.add(organization)

        openai_provider = Provider(
            id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
            name="OpenAI",
            provider_type=ProviderType.OPENAI,
            base_url="https://api.openai.com/v1",
            is_active=True,
        )
        # Catalog entries for future providers — not granted to the default team.
        anthropic_provider = Provider(
            id=uuid.UUID("11111111-1111-1111-1111-111111111112"),
            name="Anthropic",
            provider_type=ProviderType.ANTHROPIC,
            base_url="https://api.anthropic.com",
            is_active=False,
        )
        ollama_provider = Provider(
            id=uuid.UUID("11111111-1111-1111-1111-111111111113"),
            name="Ollama",
            provider_type=ProviderType.OLLAMA,
            base_url="http://localhost:11434",
            is_active=False,
        )
        mock_provider = Provider(
            id=uuid.UUID("11111111-1111-1111-1111-111111111114"),
            name="Mock",
            provider_type=ProviderType.MOCK,
            base_url="http://localhost",
            is_active=True,
        )
        db.add_all(
            [openai_provider, anthropic_provider, ollama_provider, mock_provider]
        )

        openai_models = [
            LLMModel(
                id=uuid.UUID("22222222-2222-2222-2222-222222222221"),
                provider_id=openai_provider.id,
                name="gpt-5",
                display_name="GPT-5",
                context_window=400000,
                max_output_tokens=128000,
                is_active=True,
            ),
            LLMModel(
                id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
                provider_id=openai_provider.id,
                name="gpt-5-mini",
                display_name="GPT-5 Mini",
                context_window=400000,
                max_output_tokens=128000,
                is_active=True,
            ),
            LLMModel(
                id=uuid.UUID("22222222-2222-2222-2222-222222222223"),
                provider_id=openai_provider.id,
                name="gpt-4.1",
                display_name="GPT-4.1",
                context_window=1048576,
                max_output_tokens=32768,
                is_active=True,
            ),
            LLMModel(
                id=uuid.UUID("22222222-2222-2222-2222-222222222224"),
                provider_id=openai_provider.id,
                name="gpt-4.1-mini",
                display_name="GPT-4.1 Mini",
                context_window=1048576,
                max_output_tokens=32768,
                is_active=True,
            ),
        ]
        mock_model = LLMModel(
            id=uuid.UUID("22222222-2222-2222-2222-222222222227"),
            provider_id=mock_provider.id,
            name="mock-chat",
            display_name="Mock Chat",
            context_window=8192,
            max_output_tokens=2048,
            is_active=True,
        )
        db.add_all([*openai_models, mock_model])

        gpt_5_mini = openai_models[1]

        team = Team(
            id=uuid.UUID("77777777-7777-7777-7777-777777777777"),
            organization_id=organization.id,
            name="Platform Engineering",
            slug="platform",
            is_active=True,
        )
        db.add(team)
        db.flush()

        # OpenAI-only grants for the default team (+ mock for local testing).
        db.add(
            TeamProviderPermission(
                team_id=team.id,
                provider_id=openai_provider.id,
                is_allowed=True,
            )
        )
        db.add(
            TeamProviderPermission(
                team_id=team.id,
                provider_id=mock_provider.id,
                is_allowed=True,
            )
        )
        for model in openai_models:
            db.add(TeamAllowedModel(team_id=team.id, model_id=model.id))
        db.add(TeamAllowedModel(team_id=team.id, model_id=mock_model.id))

        db.add(
            TeamPolicy(
                team_id=team.id,
                system_prompt=(
                    "You are an assistant accessed through the LLM API Gateway. "
                    "Be concise and accurate."
                ),
                compliance_prompt=(
                    "Do not reveal secrets, API keys, or confidential internal data."
                ),
                content_filter_config={
                    "max_input_chars": 100000,
                    "blocked_terms": ["exfiltrate-secrets-now"],
                    "block_output_on_match": False,
                },
                routing_config={
                    "preferred_provider": "openai",
                    "preferred_provider_strict": False,
                    "model_aliases": {"gpt-4": "gpt-4.1-mini"},
                },
                enrichment_config={
                    "default_metadata": {"env": "development"},
                },
                is_active=True,
            )
        )
        db.add(
            TeamRateLimit(
                team_id=team.id,
                requests_per_minute=120,
                tokens_per_minute=200_000,
                burst_multiplier=2.0,
                priority=RateLimitPriority.NORMAL,
                is_active=True,
            )
        )
        db.add(
            TeamBudget(
                team_id=team.id,
                daily_budget_usd=50.0,
                monthly_budget_usd=500.0,
                warning_threshold_pct=80,
                hard_enforcement=True,
                is_active=True,
            )
        )

        user = User(
            id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
            organization_id=organization.id,
            email="admin@example.com",
            full_name="Gateway Administrator",
            role=UserRole.ADMIN,
            is_active=True,
        )
        db.add(user)

        raw_key, key_prefix, key_hash = generate_api_key()
        api_key = APIKey(
            id=uuid.UUID("44444444-4444-4444-4444-444444444444"),
            user_id=user.id,
            team_id=team.id,
            name="Development Key",
            key_prefix=key_prefix,
            key_hash=key_hash,
            is_active=True,
        )
        db.add(api_key)

        request = LLMRequest(
            id=uuid.UUID("55555555-5555-5555-5555-555555555555"),
            user_id=user.id,
            api_key_id=api_key.id,
            request_id="req_000001",
            model_id=gpt_5_mini.id,
            endpoint="/chat/completions",
            prompt_tokens=120,
            completion_tokens=58,
            total_tokens=178,
            latency_ms=742.8,
            status=RequestStatus.SUCCESS,
            provider_request_id="chatcmpl_abc123",
            created_at=datetime.now(timezone.utc),
        )
        db.add(request)

        usage = UsageRecord(
            id=uuid.UUID("66666666-6666-6666-6666-666666666666"),
            request_id=request.id,
            user_id=user.id,
            api_key_id=api_key.id,
            model_id=gpt_5_mini.id,
            prompt_tokens=120,
            completion_tokens=58,
            total_tokens=178,
            input_cost_usd=0.000060,
            output_cost_usd=0.000116,
            total_cost_usd=0.000176,
            created_at=datetime.now(timezone.utc),
        )
        db.add(usage)

        db.commit()
        print("Database seeded successfully.")
        print(f"Team: {team.slug} (OpenAI + mock allowed)")
        print(f"Development API key (store securely, shown once): {raw_key}")

    except Exception:
        db.rollback()
        raise


if __name__ == "__main__":
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()
