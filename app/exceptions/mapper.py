from __future__ import annotations

import logging

from app.exceptions.base import GatewayError
from app.exceptions.gateway import ProviderError

logger = logging.getLogger(__name__)


def map_provider_exception(
    exc: Exception,
    *,
    provider: str | None = None,
) -> GatewayError:
    """
    Map vendor SDK exceptions into gateway errors.

    Provider packages own the specific isinstance checks; this function
    dispatches and guarantees a GatewayError is always returned.
    """
    if isinstance(exc, GatewayError):
        return exc

    mapped: GatewayError | None = None

    if provider == "openai" or provider is None:
        from app.providers.openai.exceptions import map_openai_exception

        mapped = map_openai_exception(exc)

    if mapped is None:
        mapped = ProviderError(
            str(exc) or "Provider request failed.",
            provider=provider,
        )

    logger.warning(
        "Mapped provider exception provider=%s type=%s -> %s",
        provider or mapped.provider,
        type(exc).__name__,
        mapped.error_type,
        exc_info=exc,
    )
    return mapped
