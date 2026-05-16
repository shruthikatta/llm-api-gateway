from __future__ import annotations

from typing import Any


class GatewayError(Exception):
    """
    Base exception for all client-facing gateway errors.

    Provider SDKs must never leak past this boundary.
    """

    status_code: int = 500
    error_type: str = "gateway_error"
    retryable: bool = False

    def __init__(
        self,
        message: str,
        *,
        details: Any = None,
        provider: str | None = None,
        request_id: str | None = None,
    ):
        self.message = message
        self.details = details
        self.provider = provider
        self.request_id = request_id
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": self.error_type,
            "message": self.message,
            "details": self.details,
            "retryable": self.retryable,
        }
        if self.provider is not None:
            payload["provider"] = self.provider
        if self.request_id is not None:
            payload["request_id"] = self.request_id
        retry_after = getattr(self, "retry_after", None)
        if retry_after is not None:
            payload["retry_after_seconds"] = retry_after
        return payload
