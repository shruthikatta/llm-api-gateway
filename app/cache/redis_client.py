from __future__ import annotations

import logging

from redis import Redis
from redis.exceptions import RedisError

from app.cache import CacheClient

logger = logging.getLogger(__name__)


class RedisCacheClient:
    """
    Redis-backed CacheClient.

    Works with local Docker Redis and Memorystore using the same redis_url.
    """

    def __init__(self, url: str, *, socket_timeout: float = 1.0):
        self._client = Redis.from_url(
            url,
            socket_timeout=socket_timeout,
            socket_connect_timeout=socket_timeout,
            decode_responses=True,
        )

    def ping(self) -> bool:
        try:
            return bool(self._client.ping())
        except RedisError:
            logger.warning("Redis ping failed", exc_info=True)
            return False

    def eval_script(
        self,
        script: str,
        keys: list[str],
        args: list[str],
    ) -> list[int | float | str] | int | float | str | None:
        try:
            return self._client.eval(script, len(keys), *keys, *args)
        except RedisError as exc:
            logger.warning("Redis eval failed", exc_info=True)
            raise CacheUnavailableError("Cache backend unavailable.") from exc

    def get(self, key: str) -> str | None:
        try:
            return self._client.get(key)
        except RedisError as exc:
            logger.warning("Redis get failed", exc_info=True)
            raise CacheUnavailableError("Cache backend unavailable.") from exc

    def set(self, key: str, value: str, *, ttl_seconds: int | None = None) -> None:
        try:
            self._client.set(key, value, ex=ttl_seconds)
        except RedisError as exc:
            logger.warning("Redis set failed", exc_info=True)
            raise CacheUnavailableError("Cache backend unavailable.") from exc

    def close(self) -> None:
        self._client.close()


class CacheUnavailableError(RuntimeError):
    """Raised when the cache backend cannot serve a request."""


def create_cache_client(url: str) -> CacheClient:
    return RedisCacheClient(url)
