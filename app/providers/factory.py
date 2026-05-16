from __future__ import annotations

from app.config.store import get_config_store
from app.core.config import settings
from app.core.constants import DEFAULT_TIMEOUT_SECONDS
from app.exceptions import UnknownProvider
from app.exceptions.gateway import ValidationError
from app.providers.anthropic.provider import AnthropicProvider
from app.providers.base import BaseProvider
from app.providers.mock.provider import MockProvider
from app.providers.ollama.provider import OllamaProvider
from app.providers.openai.provider import OpenAIProvider
from app.providers.registry import PROVIDER_REGISTRY


class ProviderFactory:
    """
    Resolve and construct provider implementations.

    Callers never branch on provider name themselves.
    """

    @staticmethod
    def get_provider(
        provider_name: str,
        *,
        api_key: str | None = None,
        timeout: float | None = None,
        base_url: str | None = None,
    ) -> BaseProvider:
        name = provider_name.lower().strip()
        provider_cls = PROVIDER_REGISTRY.get(name)

        if provider_cls is None:
            raise UnknownProvider(name)

        config = get_config_store().get()
        if not config.provider_enabled(name):
            raise ValidationError(
                f"Provider is disabled in configuration: {name}",
                provider=name,
                details={"provider": name},
            )

        resolved_timeout = (
            timeout
            if timeout is not None
            else config.provider_timeout(name, DEFAULT_TIMEOUT_SECONDS)
        )
        resolved_base_url = base_url or config.provider_base_url(name)

        if provider_cls is OpenAIProvider:
            key = api_key or settings.openai_api_key.get_secret_value()
            return OpenAIProvider(
                api_key=key,
                timeout=resolved_timeout,
                base_url=resolved_base_url,
            )

        if provider_cls is AnthropicProvider:
            key = api_key or settings.anthropic_api_key.get_secret_value()
            if not key:
                raise ValidationError(
                    "Anthropic API key is not configured.",
                    provider=name,
                )
            return AnthropicProvider(
                api_key=key,
                timeout=resolved_timeout,
                base_url=resolved_base_url,
            )

        if provider_cls is OllamaProvider:
            return OllamaProvider(
                api_key=api_key,
                timeout=resolved_timeout,
                base_url=resolved_base_url,
            )

        if provider_cls is MockProvider:
            section = config.providers.get("mock")
            latency = section.simulated_latency_ms if section else 5.0
            fail_rate = section.chaos_fail_rate if section else 0.0
            always_fail = section.chaos_always_fail if section else False
            return MockProvider(
                simulated_latency_ms=latency,
                chaos_fail_rate=fail_rate,
                chaos_always_fail=always_fail,
            )

        raise UnknownProvider(name)
