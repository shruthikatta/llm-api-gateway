from __future__ import annotations

from fastapi import APIRouter, Request, Response, status
from sqlalchemy import text

from app.cache.redis_client import create_cache_client
from app.exceptions.gateway import CircuitOpenError
from app.config.store import get_config_store
from app.core.config import settings
from app.core.constants import APP_VERSION
from app.db.session import engine
from app.health.store import ProviderHealthStore
from app.providers.registry import PROVIDER_REGISTRY
from app.schemas.health import HealthResponse, LiveResponse, ProviderHealthStatus, ReadyResponse

router = APIRouter(tags=["health"])


def _check_database() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _check_redis() -> bool:
    client = create_cache_client(settings.redis_url)
    try:
        return client.ping()
    finally:
        client.close()


def _provider_health(cache) -> list[ProviderHealthStatus]:
    config = get_config_store().get()
    window = config.resilience.circuit_breaker.rolling_window_seconds
    store = ProviderHealthStore(cache, window_seconds=window)
    statuses: list[ProviderHealthStatus] = []
    for name in PROVIDER_REGISTRY:
        if not config.provider_enabled(name):
            continue
        circuit_state = "closed"
        try:
            CircuitBreakerService(cache).allow_request(name)
        except CircuitOpenError as exc:
            circuit_state = exc.circuit_state
        snapshot = store.get_snapshot(name, circuit_state=circuit_state)
        statuses.append(
            ProviderHealthStatus(
                provider=snapshot.provider,
                healthy=snapshot.healthy and circuit_state != "open",
                latency_ms_ema=snapshot.latency_ms_ema,
                error_rate=snapshot.error_rate,
                consecutive_failures=snapshot.consecutive_failures,
            )
        )
    return statuses


@router.get("/live", response_model=LiveResponse)
def liveness() -> LiveResponse:
    """Process is up. No dependency checks."""
    return LiveResponse(status="alive", version=APP_VERSION)


@router.get("/ready", response_model=ReadyResponse)
def readiness(response: Response) -> ReadyResponse:
    """Ready to serve traffic when critical dependencies are reachable."""
    database_ok = _check_database()
    redis_ok = _check_redis()
    ready = database_ok and redis_ok
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadyResponse(
        status="ready" if ready else "not_ready",
        database="connected" if database_ok else "disconnected",
        redis="connected" if redis_ok else "disconnected",
        version=APP_VERSION,
    )


@router.get("/health", response_model=HealthResponse)
def health(request: Request, response: Response) -> HealthResponse:
    database_ok = _check_database()
    redis_ok = _check_redis()
    cache = getattr(request.app.state, "cache", None)
    providers = _provider_health(cache) if cache is not None else []
    provider_ok = all(item.healthy for item in providers) if providers else True
    healthy = database_ok and redis_ok and provider_ok
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status="healthy" if healthy else "unhealthy",
        database="connected" if database_ok else "disconnected",
        redis="connected" if redis_ok else "disconnected",
        version=APP_VERSION,
        app=settings.app_name,
        env=settings.app_env,
        providers=providers,
    )
