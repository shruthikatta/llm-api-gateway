"""
Legacy provider exception module.

New code should import from app.exceptions.
"""

from app.exceptions.gateway import (
    AuthenticationError as InvalidProviderCredentials,
    NotFoundError,
    ProviderError,
    RateLimitError as ProviderRateLimitError,
    TimeoutError as ProviderTimeoutError,
    UnknownProvider,
    ValidationError as ProviderRequestError,
)

# Unavailable maps to ProviderError (502, retryable)
ProviderUnavailableError = ProviderError

__all__ = [
    "ProviderError",
    "UnknownProvider",
    "InvalidProviderCredentials",
    "ProviderRateLimitError",
    "ProviderTimeoutError",
    "ProviderUnavailableError",
    "ProviderRequestError",
    "NotFoundError",
]
