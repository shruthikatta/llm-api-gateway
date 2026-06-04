from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from app.models.llm_model import LLMModel
from app.providers.schemas import GenerateRequest

COST_SCALE = Decimal("0.000001")


def estimate_tokens_from_request(request: GenerateRequest) -> tuple[int, int]:
    prompt_chars = sum(len(message.content) for message in request.messages)
    prompt_tokens = max(1, prompt_chars // 4)
    completion_tokens = request.max_tokens or 1024
    return prompt_tokens, completion_tokens


def calculate_cost(
    model: LLMModel,
    *,
    prompt_tokens: int,
    completion_tokens: int,
) -> tuple[Decimal, Decimal, Decimal]:
    input_cost = (
        Decimal(prompt_tokens)
        * Decimal(model.input_price_per_million_usd)
        / Decimal(1_000_000)
    ).quantize(COST_SCALE, rounding=ROUND_HALF_UP)
    output_cost = (
        Decimal(completion_tokens)
        * Decimal(model.output_price_per_million_usd)
        / Decimal(1_000_000)
    ).quantize(COST_SCALE, rounding=ROUND_HALF_UP)
    total = (input_cost + output_cost).quantize(COST_SCALE, rounding=ROUND_HALF_UP)
    return input_cost, output_cost, total


def estimate_cost(model: LLMModel, request: GenerateRequest) -> Decimal:
    prompt_tokens, completion_tokens = estimate_tokens_from_request(request)
    _, _, total = calculate_cost(
        model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )
    return total
