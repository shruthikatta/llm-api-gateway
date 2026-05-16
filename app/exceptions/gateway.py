from __future__ import annotations

from typing import Any

from app.exceptions.base import GatewayError


class AuthenticationError(GatewayError):
    status_code = 401
    error_type = "authentication_error"
    retryable = False


class AuthorizationError(GatewayError):
    status_code = 403
    error_type = "authorization_error"
    retryable = False


class ValidationError(GatewayError):
    status_code = 400
    error_type = "validation_error"
    retryable = False


class ProviderError(GatewayError):
    status_code = 502
    error_type = "provider_error"
    retryable = True


class RateLimitError(GatewayError):
    status_code = 429
    error_type = "rate_limit_error"
    retryable = True

    def __init__(
        self,
        message: str,
        *,
        retry_after: int | None = None,
        details: Any = None,
        provider: str | None = None,
        request_id: str | None = None,
    ):
        super().__init__(
            message,
            details=details,
            provider=provider,
            request_id=request_id,
        )
        self.retry_after = retry_after


class BudgetExceededError(GatewayError):
    status_code = 402
    error_type = "budget_exceeded"
    retryable = False

    def __init__(
        self,
        message: str,
        *,
        period: str,
        limit_usd: float,
        spent_usd: float,
        details: Any = None,
        request_id: str | None = None,
    ):
        payload = {
            "period": period,
            "limit_usd": limit_usd,
            "spent_usd": spent_usd,
        }
        if details:
            payload.update(details if isinstance(details, dict) else {"details": details})
        super().__init__(message, details=payload, request_id=request_id)
        self.period = period
        self.limit_usd = limit_usd
        self.spent_usd = spent_usd


class CircuitOpenError(ProviderError):
    """Provider circuit breaker is open — try a fallback route."""

    def __init__(self, provider: str, *, state: str = "open"):
        super().__init__(
            f"Provider circuit is {state}: {provider}",
            provider=provider,
            details={"provider": provider, "circuit_state": state},
        )
        self.circuit_state = state


class AllProvidersFailedError(ProviderError):
    """Every provider in the fallback chain failed."""

    def __init__(
        self,
        message: str = "All providers failed.",
        *,
        providers: list[str],
        last_error: str | None = None,
    ):
        super().__init__(
            message,
            details={"providers": providers, "last_error": last_error},
        )
        self.providers = providers


class TimeoutError(GatewayError):
    status_code = 504
    error_type = "timeout_error"
    retryable = True


class NotFoundError(GatewayError):
    status_code = 404
    error_type = "not_found"
    retryable = False


class InternalGatewayError(GatewayError):
    status_code = 500
    error_type = "internal_error"
    retryable = False


# --- Auth convenience subclasses (uniform client messages) ---


class MissingAPIKey(AuthenticationError):
    def __init__(self):
        super().__init__("Invalid or missing API key.")


class InvalidAPIKey(AuthenticationError):
    def __init__(self):
        super().__init__("Invalid or missing API key.")


class PermissionDenied(AuthorizationError):
    def __init__(self, message: str = "Permission denied."):
        super().__init__(message)


class TeamDisabledError(AuthorizationError):
    def __init__(self):
        super().__init__("Team is disabled.")


class ProviderAccessDenied(AuthorizationError):
    def __init__(self, provider: str):
        super().__init__(
            f"Team is not allowed to use provider: {provider}",
            provider=provider,
            details={"provider": provider},
        )


class ModelAccessDenied(AuthorizationError):
    def __init__(self, model: str):
        super().__init__(
            f"Team is not allowed to use model: {model}",
            details={"model": model},
        )


class ContentFilterError(ValidationError):
    def __init__(self, message: str, *, details: Any = None):
        super().__init__(message, details=details)


# --- Routing convenience subclasses ---


class ModelNotFoundError(NotFoundError):
    def __init__(self, model: str):
        super().__init__(f"Model not found: {model}", details={"model": model})
        self.model = model


class ModelInactiveError(ValidationError):
    def __init__(self, model: str):
        super().__init__(f"Model is inactive: {model}", details={"model": model})
        self.model = model


class ProviderInactiveError(ValidationError):
    def __init__(self, provider: str):
        super().__init__(
            f"Provider is inactive: {provider}",
            provider=provider,
            details={"provider": provider},
        )


class UnknownProvider(NotFoundError):
    def __init__(self, provider_name: str):
        super().__init__(
            f"Unknown provider: {provider_name}",
            provider=provider_name,
            details={"provider": provider_name},
        )
