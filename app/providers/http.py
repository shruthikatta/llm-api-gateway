from __future__ import annotations

from typing import Any

import httpx

from app.core.constants import DEFAULT_TIMEOUT_SECONDS


class AsyncHttpClient:
    """
    Shared async HTTP client for provider adapters.

    Providers must not create ad-hoc httpx clients; this wrapper owns
    timeouts, connection pooling, and teardown.
    """

    def __init__(
        self,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        headers: dict[str, str] | None = None,
        base_url: str = "",
        client: httpx.AsyncClient | None = None,
    ):
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(timeout),
            headers=headers or {},
        )

    async def request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        return await self._client.request(method, url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self._client.post(url, **kwargs)

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self._client.get(url, **kwargs)

    def stream(self, method: str, url: str, **kwargs: Any):
        return self._client.stream(method, url, **kwargs)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()
