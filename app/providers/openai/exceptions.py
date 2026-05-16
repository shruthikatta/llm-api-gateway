from __future__ import annotations

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError as OpenAIAuthenticationError,
    BadRequestError,
    OpenAIError,
    RateLimitError as OpenAIRateLimitError,
)

from app.exceptions.base import GatewayError
from app.exceptions.gateway import (
    AuthenticationError,
    ProviderError,
    RateLimitError,
    TimeoutError,
    ValidationError,
)

PROVIDER_NAME = "openai"


def map_openai_exception(exc: Exception) -> GatewayError:
    """Map OpenAI SDK exceptions to gateway errors."""

    if isinstance(exc, OpenAIAuthenticationError):
        return AuthenticationError(
            "Invalid provider credentials.",
            provider=PROVIDER_NAME,
        )

    if isinstance(exc, OpenAIRateLimitError):
        return RateLimitError(
            "Provider rate limit exceeded.",
            provider=PROVIDER_NAME,
        )

    if isinstance(exc, APITimeoutError):
        return TimeoutError(
            "Provider request timed out.",
            provider=PROVIDER_NAME,
        )

    if isinstance(exc, BadRequestError):
        return ValidationError(
            str(exc) or "Invalid provider request.",
            provider=PROVIDER_NAME,
        )

    if isinstance(exc, APIConnectionError):
        return ProviderError(
            "Provider is temporarily unavailable.",
            provider=PROVIDER_NAME,
        )

    if isinstance(exc, APIStatusError):
        status_code = getattr(exc, "status_code", None)
        if status_code == 401:
            return AuthenticationError(
                "Invalid provider credentials.",
                provider=PROVIDER_NAME,
            )
        if status_code == 429:
            return RateLimitError(
                "Provider rate limit exceeded.",
                provider=PROVIDER_NAME,
            )
        if status_code is not None and status_code >= 500:
            return ProviderError(
                "Provider is temporarily unavailable.",
                provider=PROVIDER_NAME,
            )
        return ValidationError(
            str(exc) or "Provider request failed.",
            provider=PROVIDER_NAME,
        )

    if isinstance(exc, OpenAIError):
        return ProviderError(
            str(exc) or "OpenAI error.",
            provider=PROVIDER_NAME,
        )

    return ProviderError(
        str(exc) or "Unexpected provider error.",
        provider=PROVIDER_NAME,
    )
