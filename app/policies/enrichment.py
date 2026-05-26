from __future__ import annotations

from typing import Any

from app.policies.context import ResolvedPolicy
from app.schemas.chat import ChatCompletionRequest, Message


def inject_gateway_prompts(
    request: ChatCompletionRequest,
    policy: ResolvedPolicy,
) -> ChatCompletionRequest:
    """
    Prepend team system + compliance prompts without mutating the client body.

    Order (highest priority first in the conversation prefix):
    1. Compliance prompt (policy/legal)
    2. Team system prompt
    3. Client-supplied messages (including their system messages)
    """
    prefix: list[Message] = []
    if policy.compliance_prompt:
        prefix.append(Message(role="system", content=policy.compliance_prompt))
    if policy.system_prompt:
        prefix.append(Message(role="system", content=policy.system_prompt))

    if not prefix:
        return request

    return request.model_copy(update={"messages": [*prefix, *request.messages]})


def enrich_metadata(
    request: ChatCompletionRequest,
    policy: ResolvedPolicy,
    *,
    request_id: str,
) -> dict[str, Any]:
    """Build provider-agnostic metadata for GenerateRequest.metadata."""
    defaults = dict(policy.enrichment.get("default_metadata") or {})
    client_meta = dict(request.metadata or {})
    return {
        **defaults,
        **client_meta,
        "team_id": policy.team_id,
        "team_slug": policy.team_slug,
        "gateway_request_id": request_id,
        "client_user": request.user,
    }
