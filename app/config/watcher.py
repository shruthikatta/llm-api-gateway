from __future__ import annotations

import asyncio
import logging

from app.config.store import ConfigStore
from app.exceptions.gateway import ValidationError as GatewayValidationError

logger = logging.getLogger(__name__)


async def run_config_hot_reload(store: ConfigStore) -> None:
    """
    Background task: poll gateway.yaml and apply validated reloads.

    Invalid configs are rejected; the last good config remains active.
    """
    while True:
        config = store.get()
        if not config.gateway.hot_reload:
            await asyncio.sleep(config.gateway.hot_reload_interval_seconds)
            continue

        try:
            store.reload()
        except GatewayValidationError:
            # Already logged in ConfigStore.reload
            pass
        except Exception:
            logger.exception("Unexpected error during gateway config hot reload")

        interval = store.get().gateway.hot_reload_interval_seconds
        await asyncio.sleep(interval)
