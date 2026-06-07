from __future__ import annotations

import asyncio
import logging

from app.cache import CacheClient
from app.config.store import get_config_store
from app.health.service import ProviderHealthService

logger = logging.getLogger(__name__)


async def run_health_probes(cache: CacheClient) -> None:
    """Background loop probing enabled providers."""
    service = ProviderHealthService(cache)

    while True:
        config = get_config_store().get()
        interval = config.resilience.health_probe_interval_seconds
        try:
            results = await service.probe_all_enabled()
            unhealthy = [name for name, ok in results.items() if not ok]
            if unhealthy:
                logger.warning("Unhealthy providers detected: %s", unhealthy)
        except Exception:
            logger.exception("Health probe cycle failed")

        await asyncio.sleep(interval)
