from __future__ import annotations

import logging
import time
import uuid

from sqlalchemy.orm import Session

from app.budget.cost import calculate_cost
from app.models.api_key import APIKey
from app.models.llm_model import LLMModel
from app.models.llm_request import LLMRequest, RequestStatus
from app.models.usage_record import UsageRecord
from app.schemas.gateway_response import GatewayResponse

logger = logging.getLogger(__name__)


class UsageAccountingService:
    """Persist request and usage records for analytics and budget reconciliation."""

    def __init__(self, db: Session):
        self._db = db

    def record_success(
        self,
        *,
        api_key: APIKey,
        request_id: str,
        model: LLMModel,
        response: GatewayResponse,
        endpoint: str = "/chat/completions",
    ) -> UsageRecord:
        input_cost, output_cost, total_cost = calculate_cost(
            model,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
        )

        llm_request = LLMRequest(
            user_id=api_key.user_id,
            api_key_id=api_key.id,
            request_id=request_id,
            model_id=model.id,
            endpoint=endpoint,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            total_tokens=response.usage.total_tokens,
            latency_ms=response.latency_ms,
            status=RequestStatus.SUCCESS,
            provider_request_id=response.id,
        )
        self._db.add(llm_request)
        self._db.flush()

        usage = UsageRecord(
            request_id=llm_request.id,
            user_id=api_key.user_id,
            api_key_id=api_key.id,
            model_id=model.id,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            total_tokens=response.usage.total_tokens,
            input_cost_usd=input_cost,
            output_cost_usd=output_cost,
            total_cost_usd=total_cost,
        )
        self._db.add(usage)
        self._db.flush()
        return usage

    def record_stream_estimate(
        self,
        *,
        api_key: APIKey,
        request_id: str,
        model: LLMModel,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float,
        provider_request_id: str,
        endpoint: str = "/chat/completions",
    ) -> UsageRecord:
        input_cost, output_cost, total_cost = calculate_cost(
            model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        total_tokens = prompt_tokens + completion_tokens

        llm_request = LLMRequest(
            user_id=api_key.user_id,
            api_key_id=api_key.id,
            request_id=request_id,
            model_id=model.id,
            endpoint=endpoint,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            status=RequestStatus.SUCCESS,
            provider_request_id=provider_request_id,
        )
        self._db.add(llm_request)
        self._db.flush()

        usage = UsageRecord(
            request_id=llm_request.id,
            user_id=api_key.user_id,
            api_key_id=api_key.id,
            model_id=model.id,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            input_cost_usd=input_cost,
            output_cost_usd=output_cost,
            total_cost_usd=total_cost,
        )
        self._db.add(usage)
        self._db.flush()
        return usage

    def record_rate_limited(
        self,
        *,
        api_key: APIKey,
        request_id: str,
        model_id: uuid.UUID | None,
        endpoint: str = "/chat/completions",
    ) -> None:
        llm_request = LLMRequest(
            user_id=api_key.user_id,
            api_key_id=api_key.id,
            request_id=request_id,
            model_id=model_id or api_key.id,
            endpoint=endpoint,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            latency_ms=0.0,
            status=RequestStatus.RATE_LIMITED,
            error_message="Rate limit exceeded.",
        )
        self._db.add(llm_request)
        self._db.flush()
