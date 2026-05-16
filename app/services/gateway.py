from __future__ import annotations

import logging
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.budget.accounting import UsageAccountingService
from app.budget.cost import estimate_cost, estimate_tokens_from_request
from app.budget.service import BudgetService
from app.cache import CacheClient
from app.config.store import get_config_store
from app.exceptions.base import GatewayError
from app.exceptions.gateway import (
    AllProvidersFailedError,
    AuthorizationError,
    ProviderAccessDenied,
)
from app.models.api_key import APIKey
from app.models.llm_model import LLMModel
from app.models.team import Team
from app.policies.access import AccessControlService
from app.policies.content_filter import (
    apply_input_content_filter,
    apply_output_content_filter,
)
from app.policies.context import ResolvedPolicy
from app.policies.enrichment import enrich_metadata, inject_gateway_prompts
from app.policies.routing import apply_routing_policy
from app.providers.schemas import ChatMessage, GenerateRequest, StreamChunk
from app.rate_limit.service import RateLimitService
from app.router.fallback import build_route_chain
from app.router.model_router import ModelRouter, RouteDecision
from app.schemas.chat import ChatCompletionRequest
from app.schemas.gateway_response import GatewayResponse
from app.services.resilient_llm_service import ResilientLLMService
from app.telemetry import get_tracer
from app.telemetry.metrics import (
    COST_USD_TOTAL,
    FAILOVER_TOTAL,
    REQUEST_LATENCY_SECONDS,
    REQUESTS_TOTAL,
    TOKENS_TOTAL,
)

logger = logging.getLogger(__name__)
tracer = get_tracer("ai-gateway.gateway")


@dataclass(slots=True)
class PreparedRequest:
    generate_request: GenerateRequest
    routes: list[RouteDecision]
    policy: ResolvedPolicy
    team: Team
    request_id: str
    model: LLMModel | None
    estimated_cost_usd: Decimal
    reserved_tokens: int

    @property
    def route(self) -> RouteDecision:
        return self.routes[0]


class GatewayService:
    """
    HTTP-facing gateway orchestrator with rate limits, budgets, retries,
    circuit breakers, and automatic provider failover.
    """

    def __init__(
        self,
        db: Session,
        cache: CacheClient,
        llm_service: ResilientLLMService | None = None,
    ):
        self._db = db
        self._cache = cache
        self._llm = llm_service or ResilientLLMService(cache)
        self._router = ModelRouter(db)
        self._access = AccessControlService(db)
        self._rate_limits = RateLimitService(db, cache)
        self._budgets = BudgetService(db, cache)
        self._accounting = UsageAccountingService(db)

    async def chat(
        self,
        request: ChatCompletionRequest,
        *,
        api_key: APIKey,
    ) -> GatewayResponse:
        with tracer.start_as_current_span("gateway.chat") as span:
            span.set_attribute("gateway.model", request.model)
            span.set_attribute("gateway.stream", False)
            prepared = self._prepare(request, api_key=api_key)
            span.set_attribute("gateway.team", prepared.team.slug)
            started = time.perf_counter()
            try:
                response, winning_route = await self._generate_with_failover(prepared)
                filtered = self._filter_response(response, prepared.policy.content_filter)
                self._finalize_success(api_key, prepared, filtered, winning_route)
                self._record_success_metrics(
                    prepared,
                    winning_route,
                    latency_ms=(time.perf_counter() - started) * 1000,
                )
                return filtered
            except Exception as exc:
                self._record_error_metrics(prepared, exc)
                self._release_reservations(prepared)
                raise

    async def stream(
        self,
        request: ChatCompletionRequest,
        *,
        api_key: APIKey,
    ) -> AsyncIterator[StreamChunk]:
        prepared = self._prepare(request, api_key=api_key)
        started = time.perf_counter()
        response_id = ""
        completion_text: list[str] = []
        winning_route = prepared.route

        try:
            for route in prepared.routes:
                try:
                    route_request = self._route_generate_request(prepared, route)
                    async for chunk in self._llm.stream(
                        route_request,
                        provider=route.provider_type,
                        base_url=route.base_url,
                    ):
                        if chunk.id:
                            response_id = chunk.id
                        if chunk.delta:
                            completion_text.append(chunk.delta)
                            filtered = apply_output_content_filter(
                                chunk.delta,
                                prepared.policy.content_filter,
                            )
                            yield StreamChunk(
                                id=chunk.id,
                                model=chunk.model,
                                provider=chunk.provider,
                                delta=filtered,
                                finish_reason=chunk.finish_reason,
                            )
                        else:
                            yield chunk
                    winning_route = route
                    break
                except GatewayError as exc:
                    if not exc.retryable:
                        raise
                    logger.warning(
                        "Stream failover from provider=%s error=%s",
                        route.provider_type,
                        exc.message,
                    )
                    continue
            else:
                raise AllProvidersFailedError(
                    providers=[route.provider_type for route in prepared.routes],
                )

            latency_ms = (time.perf_counter() - started) * 1000
            prompt_tokens, _ = estimate_tokens_from_request(prepared.generate_request)
            completion_tokens = max(1, sum(len(part) for part in completion_text) // 4)
            actual_tokens = prompt_tokens + completion_tokens
            model = self._load_model(winning_route) or prepared.model
            if model is not None:
                usage = self._accounting.record_stream_estimate(
                    api_key=api_key,
                    request_id=prepared.request_id,
                    model=model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    latency_ms=latency_ms,
                    provider_request_id=response_id or prepared.request_id,
                )
                self._rate_limits.adjust_tokens(
                    prepared.team.id,
                    reserved=prepared.reserved_tokens,
                    actual=actual_tokens,
                )
                self._budgets.reconcile_actual_cost(
                    prepared.team.id,
                    estimated_cost_usd=float(prepared.estimated_cost_usd),
                    actual_cost_usd=float(usage.total_cost_usd),
                )
        except Exception:
            self._release_reservations(prepared)
            raise

    async def _generate_with_failover(
        self,
        prepared: PreparedRequest,
    ) -> tuple[GatewayResponse, RouteDecision]:
        retry_budget = get_config_store().get().resilience.retry_budget
        errors: list[str] = []

        for route in prepared.routes:
            try:
                route_request = self._route_generate_request(prepared, route)
                response = await self._llm.generate(
                    route_request,
                    provider=route.provider_type,
                    base_url=route.base_url,
                    retry_budget=retry_budget,
                )
                if route.provider_type != prepared.route.provider_type:
                    logger.info(
                        "Failover succeeded request=%s provider=%s",
                        prepared.request_id,
                        route.provider_type,
                    )
                    FAILOVER_TOTAL.labels(
                        from_provider=prepared.route.provider_type,
                        to_provider=route.provider_type,
                    ).inc()
                return response, route
            except GatewayError as exc:
                errors.append(f"{route.provider_type}: {exc.message}")
                if not exc.retryable:
                    raise
                logger.warning(
                    "Failover from provider=%s error=%s",
                    route.provider_type,
                    exc.message,
                )
                continue

        raise AllProvidersFailedError(
            providers=[route.provider_type for route in prepared.routes],
            last_error=errors[-1] if errors else None,
        )

    def _prepare(
        self,
        request: ChatCompletionRequest,
        *,
        api_key: APIKey,
    ) -> PreparedRequest:
        team = self._access.require_active_team(api_key)
        policy = self._access.load_policy(team)

        model_name, _hints = apply_routing_policy(request.model, policy)
        routed_request = request.model_copy(update={"model": model_name})

        apply_input_content_filter(routed_request, policy.content_filter)

        enriched_request = inject_gateway_prompts(routed_request, policy)
        routes = self._build_allowed_routes(team, request.model, enriched_request.model, policy)

        primary = routes[0]
        preferred = policy.routing.get("preferred_provider")
        if (
            preferred
            and primary.provider_type != preferred
            and bool(policy.routing.get("preferred_provider_strict", False))
        ):
            raise ProviderAccessDenied(primary.provider_type)

        request_id = f"req_{uuid.uuid4().hex[:16]}"
        metadata = enrich_metadata(enriched_request, policy, request_id=request_id)
        generate_request = self._to_generate_request(
            enriched_request,
            primary,
            metadata=metadata,
        )

        model = self._load_model(primary)
        estimated_cost = Decimal("0")
        if model is not None:
            estimated_cost = estimate_cost(model, generate_request)

        self._rate_limits.check_request(team.id)
        reserved_tokens = self._rate_limits.estimate_request_tokens(generate_request)
        self._rate_limits.reserve_tokens(team.id, reserved_tokens)
        self._budgets.check_and_reserve(
            team.id,
            float(estimated_cost),
            request_id=request_id,
        )

        return PreparedRequest(
            generate_request=generate_request,
            routes=routes,
            policy=policy,
            team=team,
            request_id=request_id,
            model=model,
            estimated_cost_usd=estimated_cost,
            reserved_tokens=reserved_tokens,
        )

    def _build_allowed_routes(
        self,
        team: Team,
        original_model: str,
        resolved_model: str,
        policy: ResolvedPolicy,
    ) -> list[RouteDecision]:
        chain = build_route_chain(self._router, resolved_model, policy)
        allowed: list[RouteDecision] = []
        for route in chain:
            try:
                self._access.assert_route_allowed(team, original_model, route)
                allowed.append(route)
            except AuthorizationError:
                continue
        if not allowed:
            self._access.assert_route_allowed(team, original_model, chain[0])
        return allowed

    def _route_generate_request(
        self,
        prepared: PreparedRequest,
        route: RouteDecision,
    ) -> GenerateRequest:
        if route.model_name == prepared.generate_request.model:
            return prepared.generate_request
        return GenerateRequest(
            model=route.model_name,
            messages=prepared.generate_request.messages,
            temperature=prepared.generate_request.temperature,
            max_tokens=prepared.generate_request.max_tokens,
            top_p=prepared.generate_request.top_p,
            stop=prepared.generate_request.stop,
            metadata=prepared.generate_request.metadata,
        )

    def _release_reservations(self, prepared: PreparedRequest) -> None:
        self._rate_limits.adjust_tokens(
            prepared.team.id,
            reserved=prepared.reserved_tokens,
            actual=0,
        )
        self._budgets.reconcile_actual_cost(
            prepared.team.id,
            estimated_cost_usd=float(prepared.estimated_cost_usd),
            actual_cost_usd=0.0,
        )

    def _finalize_success(
        self,
        api_key: APIKey,
        prepared: PreparedRequest,
        response: GatewayResponse,
        route: RouteDecision,
    ) -> None:
        model = self._load_model(route) or prepared.model
        if model is None:
            logger.warning(
                "Skipping usage accounting for unregistered model=%s",
                route.model_name,
            )
            return

        usage = self._accounting.record_success(
            api_key=api_key,
            request_id=prepared.request_id,
            model=model,
            response=response,
        )
        self._rate_limits.adjust_tokens(
            prepared.team.id,
            reserved=prepared.reserved_tokens,
            actual=response.usage.total_tokens,
        )
        self._budgets.reconcile_actual_cost(
            prepared.team.id,
            estimated_cost_usd=float(prepared.estimated_cost_usd),
            actual_cost_usd=float(usage.total_cost_usd),
        )
        self._record_usage_metrics(
            team_slug=prepared.team.slug,
            model_name=model.name,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            cost_usd=float(usage.total_cost_usd),
        )

    def _load_model(self, route: RouteDecision) -> LLMModel | None:
        if route.model_id is None:
            return None
        return self._db.get(LLMModel, route.model_id)

    def _filter_response(
        self,
        response: GatewayResponse,
        filter_config: dict,
    ) -> GatewayResponse:
        if not response.choices:
            return response
        choices = []
        for choice in response.choices:
            filtered = apply_output_content_filter(
                choice.message.content,
                filter_config,
            )
            choices.append(
                choice.model_copy(
                    update={
                        "message": choice.message.model_copy(
                            update={"content": filtered}
                        )
                    }
                )
            )
        return response.model_copy(update={"choices": choices})

    def _to_generate_request(
        self,
        request: ChatCompletionRequest,
        route: RouteDecision,
        *,
        metadata: dict,
    ) -> GenerateRequest:
        stop = request.stop
        if isinstance(stop, str):
            stop = [stop]

        return GenerateRequest(
            model=route.model_name,
            messages=[
                ChatMessage(role=message.role, content=message.content)
                for message in request.messages
            ],
            temperature=request.temperature if request.temperature is not None else 1.0,
            max_tokens=request.max_tokens,
            top_p=request.top_p,
            stop=stop,
            metadata=metadata,
        )

    def _record_success_metrics(
        self,
        prepared: PreparedRequest,
        route: RouteDecision,
        *,
        latency_ms: float,
    ) -> None:
        REQUESTS_TOTAL.labels(
            endpoint="/v1/chat/completions",
            status="200",
            provider=route.provider_type,
        ).inc()
        REQUEST_LATENCY_SECONDS.labels(
            provider=route.provider_type,
            model=route.model_name,
        ).observe(latency_ms / 1000)

    def _record_error_metrics(self, prepared: PreparedRequest | None, exc: Exception) -> None:
        provider = prepared.route.provider_type if prepared else "unknown"
        status = "500"
        if isinstance(exc, GatewayError):
            status = str(exc.status_code)
        REQUESTS_TOTAL.labels(
            endpoint="/v1/chat/completions",
            status=status,
            provider=provider,
        ).inc()

    def _record_usage_metrics(
        self,
        *,
        team_slug: str,
        model_name: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float,
    ) -> None:
        TOKENS_TOTAL.labels(
            team_slug=team_slug,
            model=model_name,
            token_type="prompt",
        ).inc(prompt_tokens)
        TOKENS_TOTAL.labels(
            team_slug=team_slug,
            model=model_name,
            token_type="completion",
        ).inc(completion_tokens)
        COST_USD_TOTAL.labels(team_slug=team_slug, model=model_name).inc(cost_usd)
