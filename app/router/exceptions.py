from __future__ import annotations

from app.exceptions.gateway import (
    ModelInactiveError,
    ModelNotFoundError,
    ProviderInactiveError,
    ValidationError,
)

# Backward-compatible alias used by older call sites / tests.
RoutingError = ValidationError

__all__ = [
    "RoutingError",
    "ModelNotFoundError",
    "ModelInactiveError",
    "ProviderInactiveError",
]
