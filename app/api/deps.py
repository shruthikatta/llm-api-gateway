from __future__ import annotations

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_api_key, get_current_user, get_db
from app.cache import CacheClient
from app.services.gateway import GatewayService
from app.services.resilient_llm_service import ResilientLLMService
from app.services.model_service import ModelService
from app.services.provider_service import ProviderService

__all__ = [
    "get_db",
    "get_current_api_key",
    "get_current_user",
    "get_cache",
    "get_gateway_service",
    "get_provider_service",
    "get_model_service",
]


def get_cache(request: Request) -> CacheClient:
    return request.app.state.cache


def get_gateway_service(
    db: Session = Depends(get_db),
    cache: CacheClient = Depends(get_cache),
) -> GatewayService:
    return GatewayService(db, cache, ResilientLLMService(cache))


def get_provider_service(db: Session) -> ProviderService:
    return ProviderService(db)


def get_model_service(db: Session) -> ModelService:
    return ModelService(db)
