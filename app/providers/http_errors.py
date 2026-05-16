from __future__ import annotations

import logging

import httpx

from app.exceptions.gateway import (
    AuthenticationError,
    ProviderError,
    RateLimitError,
    TimeoutError,
    ValidationError,
)

logger = logging.getLogger(__name__)


def map_httpx_exception(exc: Exception, *, provider: str) -> Exception | None:
    """Map transport-level httpx errors into gateway errors."""
    if isinstance(exc, httpx.TimeoutException):
        return TimeoutError("Provider request timed out.", provider=provider)
    if isinstance(exc, httpx.HTTPStatusError):
        return map_http_status_error(exc, provider=provider)
    if isinstance(exc, httpx.RequestError):
        return ProviderError(
            f"Provider connection failed: {exc}",
            provider=provider,
        )
    return None


def map_http_status_error(
    exc: httpx.HTTPStatusError,
    *,
    provider: str,
) -> Exception:
    status = exc.response.status_code
    body = _safe_body(exc.response)

    if status in (401, 403):
        return AuthenticationError(
            "Provider authentication failed.",
            provider=provider,
            details={"status_code": status, "body": body},
        )
    if status == 429:
        return RateLimitError(
            "Provider rate limit exceeded.",
            provider=provider,
            details={"status_code": status, "body": body},
        )
    if status == 400:
        return ValidationError(
            "Provider rejected the request.",
            provider=provider,
            details={"status_code": status, "body": body},
        )
    if status >= 500:
        return ProviderError(
            "Provider upstream error.",
            provider=provider,
            details={"status_code": status, "body": body},
        )
    return ProviderError(
        f"Provider returned HTTP {status}.",
        provider=provider,
        details={"status_code": status, "body": body},
    )


def _safe_body(response: httpx.Response) -> str:
    try:
        text = response.text
    except Exception:
        return ""
    return text[:500]
