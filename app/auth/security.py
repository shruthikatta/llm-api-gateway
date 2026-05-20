from __future__ import annotations

import hashlib
import secrets

API_KEY_PREFIX = "sk_live_"
API_KEY_LENGTH = 32


def generate_api_key() -> tuple[str, str, str]:
    """
    Generates a new API key.

    Returns:
        raw_key: Full API key shown only once to the user.
        key_prefix: Prefix stored for identification.
        key_hash: SHA-256 hash stored in the database.
    """
    secret = secrets.token_urlsafe(API_KEY_LENGTH)
    raw_key = f"{API_KEY_PREFIX}{secret}"
    return (
        raw_key,
        get_key_prefix(raw_key),
        hash_api_key(raw_key),
    )


def hash_api_key(api_key: str) -> str:
    """Returns the SHA-256 hash of an API key."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def get_key_prefix(api_key: str, length: int = 12) -> str:
    """Returns the searchable prefix of an API key."""
    return api_key[:length]
