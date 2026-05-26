from __future__ import annotations

from typing import Any

from app.policies.context import ResolvedPolicy


def apply_routing_policy(
    model_name: str,
    policy: ResolvedPolicy,
) -> tuple[str, dict[str, Any]]:
    """
    Apply team routing overrides before ModelRouter.resolve.

    Returns (resolved_model_name, routing_hints).

    routing_config example:
      {
        "model_aliases": {"gpt-4": "gpt-4.1-mini"},
        "preferred_provider": "openai"
      }
    """
    routing = policy.routing
    aliases = routing.get("model_aliases") or {}
    resolved = str(aliases.get(model_name, model_name))
    hints = {
        "preferred_provider": routing.get("preferred_provider"),
        "original_model": model_name,
        "aliased_model": resolved if resolved != model_name else None,
    }
    return resolved, hints
