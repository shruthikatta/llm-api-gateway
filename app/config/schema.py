from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class GatewaySection(BaseModel):
    default_timeout_seconds: float = Field(default=60, gt=0)
    hot_reload: bool = True
    hot_reload_interval_seconds: float = Field(default=2, gt=0.1)


class LoggingSection(BaseModel):
    level: str = "INFO"
    json_logs: bool = Field(default=True, alias="json")

    model_config = {"populate_by_name": True}

    @field_validator("level")
    @classmethod
    def validate_level(cls, value: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        normalized = value.upper()
        if normalized not in allowed:
            raise ValueError(f"Invalid log level: {value}")
        return normalized


class TelemetrySection(BaseModel):
    enabled: bool = True
    service_name: str = "ai-gateway"
    otlp_endpoint: str | None = None


class ProviderSection(BaseModel):
    enabled: bool = True
    timeout_seconds: float = Field(default=60, gt=0)
    default_base_url: str | None = None
    simulated_latency_ms: float = Field(default=0, ge=0)
    chaos_fail_rate: float = Field(default=0.0, ge=0, le=1)
    chaos_always_fail: bool = False


class RoutingHeuristic(BaseModel):
    prefix: str = Field(min_length=1)
    provider: str = Field(min_length=1)

    @field_validator("provider")
    @classmethod
    def normalize_provider(cls, value: str) -> str:
        return value.lower().strip()


class FallbackChain(BaseModel):
    prefixes: list[str] = Field(default_factory=list)
    providers: list[str] = Field(min_length=1)
    fallback_model: str | None = None

    @field_validator("providers")
    @classmethod
    def normalize_providers(cls, value: list[str]) -> list[str]:
        return [provider.lower().strip() for provider in value]


class RoutingSection(BaseModel):
    heuristics: list[RoutingHeuristic] = Field(default_factory=list)
    fallback_chains: list[FallbackChain] = Field(default_factory=list)


class CircuitBreakerSection(BaseModel):
    failure_threshold: int = Field(default=5, gt=0)
    recovery_timeout_seconds: int = Field(default=30, gt=0)
    half_open_max_calls: int = Field(default=2, gt=0)
    rolling_window_seconds: int = Field(default=60, gt=0)


class ResilienceSection(BaseModel):
    request_timeout_seconds: float = Field(default=60, gt=0)
    max_retries: int = Field(default=2, ge=0)
    retry_base_delay_ms: float = Field(default=100, gt=0)
    retry_max_delay_ms: float = Field(default=5000, gt=0)
    retry_budget: int = Field(default=3, ge=0)
    health_probe_interval_seconds: float = Field(default=30, gt=1)
    circuit_breaker: CircuitBreakerSection = Field(default_factory=CircuitBreakerSection)


class RateLimitSection(BaseModel):
    default_requests_per_minute: int = Field(default=60, gt=0)
    default_tokens_per_minute: int = Field(default=100_000, gt=0)
    default_burst_multiplier: float = Field(default=2.0, gt=0)
    default_priority: str = "normal"

    @field_validator("default_priority")
    @classmethod
    def validate_priority(cls, value: str) -> str:
        allowed = {"low", "normal", "high"}
        normalized = value.lower().strip()
        if normalized not in allowed:
            raise ValueError(f"Invalid rate limit priority: {value}")
        return normalized


class BudgetSection(BaseModel):
    default_daily_budget_usd: float = Field(default=100.0, ge=0)
    default_monthly_budget_usd: float = Field(default=1000.0, ge=0)
    default_warning_threshold_pct: int = Field(default=80, ge=0, le=100)
    default_hard_enforcement: bool = True


class AlertingSection(BaseModel):
    enabled: bool = False
    budget_warnings: bool = True
    circuit_open_alerts: bool = True
    error_rate_threshold: float = Field(default=0.5, ge=0, le=1)


class GatewayYamlConfig(BaseModel):
    """Validated gateway.yaml document."""

    gateway: GatewaySection = Field(default_factory=GatewaySection)
    logging: LoggingSection = Field(default_factory=LoggingSection)
    telemetry: TelemetrySection = Field(default_factory=TelemetrySection)
    providers: dict[str, ProviderSection] = Field(default_factory=dict)
    routing: RoutingSection = Field(default_factory=RoutingSection)
    rate_limit: RateLimitSection = Field(default_factory=RateLimitSection)
    budget: BudgetSection = Field(default_factory=BudgetSection)
    alerting: AlertingSection = Field(default_factory=AlertingSection)
    resilience: ResilienceSection = Field(default_factory=ResilienceSection)

    def provider_enabled(self, name: str) -> bool:
        section = self.providers.get(name.lower())
        if section is None:
            return False
        return section.enabled

    def provider_timeout(self, name: str, default: float = 60.0) -> float:
        section = self.providers.get(name.lower())
        if section is None:
            return default
        return section.timeout_seconds

    def provider_base_url(self, name: str) -> str | None:
        section = self.providers.get(name.lower())
        if section is None:
            return None
        return section.default_base_url
