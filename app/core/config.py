from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.constants import LOG_LEVELS, SUPPORTED_PROVIDERS

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    # Application
    app_name: str = "LLM API Gateway"
    app_env: str = "development"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Logging (overridden by gateway.yaml when present)
    log_level: str = "INFO"

    # Infrastructure
    database_url: str
    redis_url: str

    # Provider secrets (never store in YAML)
    openai_api_key: SecretStr = Field(default_factory=lambda: SecretStr(""))
    anthropic_api_key: SecretStr = Field(default_factory=lambda: SecretStr(""))

    # Security
    jwt_secret: SecretStr
    slack_webhook_url: SecretStr | None = None

    # Defaults
    default_provider: str = "openai"
    default_model: str = "gpt-4.1-mini"

    # YAML config path
    gateway_config_path: str = str(BASE_DIR / "config" / "gateway.yaml")

    model_config = SettingsConfigDict(
        env_file=(
            BASE_DIR / ".env.development",
            BASE_DIR / ".env.local",
        ),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        value = value.upper()
        if value not in LOG_LEVELS:
            raise ValueError(f"Invalid log level: {value}")
        return value

    @field_validator("default_provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        value = value.lower()
        if value not in SUPPORTED_PROVIDERS:
            raise ValueError(f"Unsupported provider: {value}")
        return value

    @field_validator("port")
    @classmethod
    def validate_port(cls, value: int) -> int:
        if not 1 <= value <= 65535:
            raise ValueError("Port must be between 1 and 65535.")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
