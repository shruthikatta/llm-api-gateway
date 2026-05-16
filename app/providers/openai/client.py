from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI


class OpenAIClient:
    """
    Thin wrapper around the OpenAI async SDK.

    All SDK coupling lives here so SDK upgrades touch one file.
    """

    def __init__(
        self,
        api_key: str,
        *,
        timeout: float = 60.0,
        base_url: str | None = None,
        client: AsyncOpenAI | None = None,
    ):
        self._client = client or AsyncOpenAI(
            api_key=api_key,
            timeout=timeout,
            base_url=base_url,
        )

    async def chat(self, **kwargs: Any) -> Any:
        return await self._client.chat.completions.create(**kwargs)

    async def stream_chat(self, **kwargs: Any) -> AsyncIterator[Any]:
        kwargs = {**kwargs, "stream": True}
        stream = await self._client.chat.completions.create(**kwargs)
        async for chunk in stream:
            yield chunk

    async def embeddings(self, **kwargs: Any) -> Any:
        return await self._client.embeddings.create(**kwargs)

    async def models(self) -> Any:
        return await self._client.models.list()

    async def close(self) -> None:
        await self._client.close()
