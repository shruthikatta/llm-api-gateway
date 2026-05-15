from contextlib import asynccontextmanager
import asyncio
import logging

from fastapi import FastAPI
from sqlalchemy import text

from app.api.v1 import health
from app.api.v1.metrics import router as metrics_router
from app.api.v1.router import api_router
from app.cache.redis_client import create_cache_client
from app.config.store import get_config_store
from app.config.watcher import run_config_hot_reload
from app.core.config import settings
from app.core.constants import API_PREFIX, APP_VERSION, HEALTH_ENDPOINT
from app.dashboard.router import router as dashboard_router
from app.db.session import engine
from app.exceptions.handlers import register_exception_handlers
from app.telemetry import instrument_fastapi, setup_telemetry, shutdown_telemetry
from app.telemetry.logging import configure_logging
from app.telemetry.middleware import PrometheusMiddleware
from app.workers.health_probe import run_health_probes

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    store = get_config_store(settings.gateway_config_path)
    yaml_config = store.get()

    configure_logging(
        level=yaml_config.logging.level,
        json_logs=yaml_config.logging.json_logs,
    )
    setup_telemetry(yaml_config.telemetry)
    instrument_fastapi(app)

    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    cache = create_cache_client(settings.redis_url)
    app.state.cache = cache
    if not cache.ping():
        logger.warning("Redis is not reachable at startup; readiness will fail")

    reload_task = asyncio.create_task(run_config_hot_reload(store))
    probe_task = asyncio.create_task(run_health_probes(cache))
    app.state.config_store = store

    logger.info(
        "Gateway started env=%s version=%s",
        settings.app_env,
        APP_VERSION,
    )

    try:
        yield
    finally:
        reload_task.cancel()
        probe_task.cancel()
        for task in (reload_task, probe_task):
            try:
                await task
            except asyncio.CancelledError:
                pass
        cache.close()
        engine.dispose()
        shutdown_telemetry()
        logger.info("Gateway shutdown complete")


app = FastAPI(
    title=settings.app_name,
    version=APP_VERSION,
    lifespan=lifespan,
)

register_exception_handlers(app)
app.add_middleware(PrometheusMiddleware)

app.include_router(health.router)
app.include_router(metrics_router)
app.include_router(dashboard_router)
app.include_router(api_router, prefix=API_PREFIX)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "app": settings.app_name,
        "env": settings.app_env,
        "version": APP_VERSION,
        "health": HEALTH_ENDPOINT,
        "ready": "/ready",
        "live": "/live",
        "docs": "/docs",
        "dashboard": "/dashboard",
        "metrics": "/metrics",
        "api": API_PREFIX,
    }
