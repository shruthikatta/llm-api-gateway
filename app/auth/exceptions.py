"""
Auth-domain exception aliases.

Prefer importing from app.exceptions for new code.
"""

from app.exceptions.gateway import (
    AuthenticationError,
    AuthorizationError,
    InvalidAPIKey,
    MissingAPIKey,
    PermissionDenied,
)

__all__ = [
    "AuthenticationError",
    "AuthorizationError",
    "MissingAPIKey",
    "InvalidAPIKey",
    "PermissionDenied",
]
