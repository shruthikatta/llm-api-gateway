from __future__ import annotations

from sqlalchemy.orm import Session

from app.config.store import get_config_store
from app.models.provider import Provider, ProviderType
from app.policies.context import ResolvedPolicy
from app.router.model_router import ModelRouter, RouteDecision


def build_route_chain(
    router: ModelRouter,
    model_name: str,
    policy: ResolvedPolicy,
) -> list[RouteDecision]:
    """
    Build an ordered provider chain: primary route first, then configured fallbacks.
    """
    primary = router.resolve(model_name)
    chain = [primary]
    seen = {primary.provider_type}

    config = get_config_store().get()
    team_fallbacks = policy.routing.get("fallback_providers") or []
    chain_config = _match_fallback_chain(model_name, config.routing.fallback_chains)

    provider_order: list[str] = []
    if chain_config is not None:
        provider_order.extend(chain_config.providers)
    provider_order.extend(str(p) for p in team_fallbacks)

    for provider_type in provider_order:
        normalized = provider_type.lower().strip()
        if normalized in seen:
            continue
        route = router.resolve_for_provider(
            model_name,
            provider_type=normalized,
            fallback_model=chain_config.fallback_model if chain_config else None,
        )
        if route is not None:
            chain.append(route)
            seen.add(route.provider_type)

    return chain


def _match_fallback_chain(model_name: str, chains) -> object | None:
    for chain in chains:
        if any(model_name.startswith(prefix) for prefix in chain.prefixes):
            return chain
    return None
