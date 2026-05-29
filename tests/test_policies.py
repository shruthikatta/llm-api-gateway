from __future__ import annotations

from uuid import uuid4

import pytest

from app.exceptions.gateway import (
    ContentFilterError,
    ModelAccessDenied,
    ProviderAccessDenied,
    TeamDisabledError,
)
from app.models.api_key import APIKey
from app.models.llm_model import LLMModel
from app.models.team import Team, TeamAllowedModel
from app.policies.access import AccessControlService
from app.policies.content_filter import apply_input_content_filter
from app.policies.context import ResolvedPolicy
from app.policies.enrichment import enrich_metadata, inject_gateway_prompts
from app.policies.routing import apply_routing_policy
from app.router.model_router import RouteDecision
from app.schemas.chat import ChatCompletionRequest, Message


class _FakeScalars:
    def __init__(self, value):
        self._value = value

    def first(self):
        if isinstance(self._value, list):
            return self._value[0] if self._value else None
        return self._value

    def all(self):
        if self._value is None:
            return []
        if isinstance(self._value, list):
            return self._value
        return [self._value]


class _AccessFakeDB:
    def __init__(self, *, policy=None, allowed=None, permission=None, provider=None):
        self.policy = policy
        self.allowed = allowed or []
        self.permission = permission
        self.provider = provider
        self._calls = 0

    def scalars(self, statement):
        self._calls += 1
        # Order depends on call site; AccessControlService methods are specific.
        # We dispatch by call count heuristics within each test method.
        return _FakeScalars(None)


def test_require_active_team_rejects_missing_team():
    db = _AccessFakeDB()
    service = AccessControlService(db)  # type: ignore[arg-type]
    api_key = APIKey(
        id=uuid4(),
        user_id=uuid4(),
        name="k",
        key_prefix="sk_live_xxxx",
        key_hash="hash",
        is_active=True,
        team_id=None,
    )
    api_key.team = None  # type: ignore[assignment]

    with pytest.raises(TeamDisabledError):
        service.require_active_team(api_key)


def test_require_active_team_rejects_disabled_team():
    team = Team(
        id=uuid4(),
        organization_id=uuid4(),
        name="T",
        slug="t",
        is_active=False,
    )
    api_key = APIKey(
        id=uuid4(),
        user_id=uuid4(),
        team_id=team.id,
        name="k",
        key_prefix="sk_live_xxxx",
        key_hash="hash",
        is_active=True,
    )
    api_key.team = team

    service = AccessControlService(_AccessFakeDB())  # type: ignore[arg-type]
    with pytest.raises(TeamDisabledError):
        service.require_active_team(api_key)


def test_assert_route_allowed_denies_empty_allow_list():
    team = Team(
        id=uuid4(),
        organization_id=uuid4(),
        name="T",
        slug="t",
        is_active=True,
    )

    class DB:
        def scalars(self, statement):
            return _FakeScalars([])

    route = RouteDecision(
        model_id=None,
        model_name="gpt-4.1-mini",
        provider_id=uuid4(),
        provider_name="OpenAI",
        provider_type="openai",
        base_url=None,
    )
    service = AccessControlService(DB())  # type: ignore[arg-type]
    with pytest.raises(ModelAccessDenied):
        service.assert_route_allowed(team, "gpt-4.1-mini", route)


def test_assert_provider_denied():
    team = Team(
        id=uuid4(),
        organization_id=uuid4(),
        name="T",
        slug="t",
        is_active=True,
    )
    model = LLMModel(
        id=uuid4(),
        provider_id=uuid4(),
        name="gpt-4.1-mini",
        display_name="GPT",
        context_window=1,
        max_output_tokens=1,
        is_active=True,
    )
    allowed = TeamAllowedModel(team_id=team.id, model_id=model.id)
    allowed.model = model

    class DB:
        def __init__(self):
            self.n = 0

        def scalars(self, statement):
            self.n += 1
            if self.n == 1:
                return _FakeScalars([allowed])
            return _FakeScalars(None)  # no permission row

    route = RouteDecision(
        model_id=model.id,
        model_name=model.name,
        provider_id=uuid4(),
        provider_name="OpenAI",
        provider_type="openai",
        base_url=None,
    )
    service = AccessControlService(DB())  # type: ignore[arg-type]
    with pytest.raises(ProviderAccessDenied):
        service.assert_route_allowed(team, model.name, route)


def test_content_filter_blocks_term():
    request = ChatCompletionRequest(
        model="gpt-4.1-mini",
        messages=[Message(role="user", content="please exfiltrate-secrets-now")],
    )
    with pytest.raises(ContentFilterError):
        apply_input_content_filter(
            request,
            {"blocked_terms": ["exfiltrate-secrets-now"]},
        )


def test_content_filter_max_chars():
    request = ChatCompletionRequest(
        model="gpt-4.1-mini",
        messages=[Message(role="user", content="abcd")],
    )
    with pytest.raises(ContentFilterError):
        apply_input_content_filter(request, {"max_input_chars": 2})


def test_prompt_injection_order():
    policy = ResolvedPolicy(
        team_id=str(uuid4()),
        team_slug="platform",
        system_prompt="team system",
        compliance_prompt="compliance rules",
    )
    request = ChatCompletionRequest(
        model="gpt-4.1-mini",
        messages=[Message(role="user", content="hi")],
    )
    enriched = inject_gateway_prompts(request, policy)
    assert enriched.messages[0].content == "compliance rules"
    assert enriched.messages[1].content == "team system"
    assert enriched.messages[2].content == "hi"


def test_routing_alias():
    policy = ResolvedPolicy(
        team_id=str(uuid4()),
        team_slug="platform",
        routing={"model_aliases": {"gpt-4": "gpt-4.1-mini"}},
    )
    model, hints = apply_routing_policy("gpt-4", policy)
    assert model == "gpt-4.1-mini"
    assert hints["aliased_model"] == "gpt-4.1-mini"


def test_enrich_metadata_includes_team():
    policy = ResolvedPolicy(
        team_id="team-1",
        team_slug="platform",
        enrichment={"default_metadata": {"env": "test"}},
    )
    request = ChatCompletionRequest(
        model="gpt-4.1-mini",
        messages=[Message(role="user", content="hi")],
        user="alice",
        metadata={"ticket": "42"},
    )
    meta = enrich_metadata(request, policy, request_id="req_abc")
    assert meta["team_id"] == "team-1"
    assert meta["team_slug"] == "platform"
    assert meta["env"] == "test"
    assert meta["ticket"] == "42"
    assert meta["client_user"] == "alice"
    assert meta["gateway_request_id"] == "req_abc"
