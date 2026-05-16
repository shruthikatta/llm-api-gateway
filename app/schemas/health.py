from __future__ import annotations

from pydantic import BaseModel


class LiveResponse(BaseModel):
    status: str
    version: str = "0.1.0"


class ReadyResponse(BaseModel):
    status: str
    database: str
    redis: str
    version: str = "0.1.0"


class ProviderHealthStatus(BaseModel):
    provider: str
    healthy: bool
    latency_ms_ema: float
    error_rate: float
    consecutive_failures: int


class HealthResponse(BaseModel):
    status: str
    database: str
    redis: str
    version: str = "0.1.0"
    app: str | None = None
    env: str | None = None
    providers: list[ProviderHealthStatus] = []
