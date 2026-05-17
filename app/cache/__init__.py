from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class CacheClient(Protocol):
    """
    Replaceable cache interface.

    Local Docker Redis and GCP Memorystore both satisfy this protocol;
    call sites must depend on CacheClient, never a concrete Redis driver.
    """

    def ping(self) -> bool:
        """Return True when the cache backend is reachable."""

    def eval_script(
        self,
        script: str,
        keys: list[str],
        args: list[str],
    ) -> list[int | float | str] | int | float | str | None:
        """Run a Lua script atomically against the cache backend."""

    def get(self, key: str) -> str | None:
        """Return a string value or None when the key is absent."""

    def set(self, key: str, value: str, *, ttl_seconds: int | None = None) -> None:
        """Store a string value with an optional TTL."""

    def close(self) -> None:
        """Release connections."""
