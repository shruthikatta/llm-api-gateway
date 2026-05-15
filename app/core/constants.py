"""
Application-wide constants.
"""

SUPPORTED_PROVIDERS = (
    "openai",
    "anthropic",
    "ollama",
    "mock",
)

LOG_LEVELS = (
    "DEBUG",
    "INFO",
    "WARNING",
    "ERROR",
    "CRITICAL",
)

DEFAULT_TIMEOUT_SECONDS = 60

API_PREFIX = "/v1"

HEALTH_ENDPOINT = "/health"
READY_ENDPOINT = "/ready"
LIVE_ENDPOINT = "/live"

CHAT_COMPLETIONS_ENDPOINT = "/chat/completions"

APP_VERSION = "0.1.0"
