from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from app.config.schema import GatewayYamlConfig
from app.exceptions.gateway import ValidationError as GatewayValidationError

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "gateway.yaml"


def load_gateway_config(path: Path | str | None = None) -> GatewayYamlConfig:
    """
    Load and validate gateway.yaml.

    Invalid YAML or schema failures raise GatewayValidationError so callers
    can refuse to apply a bad reload and keep the previous config.
    """
    config_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH

    try:
        raw = config_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise GatewayValidationError(
            f"Gateway config file not found: {config_path}",
            details={"path": str(config_path)},
        ) from exc
    except OSError as exc:
        raise GatewayValidationError(
            f"Failed to read gateway config: {config_path}",
            details={"path": str(config_path), "error": str(exc)},
        ) from exc

    try:
        data = yaml.safe_load(raw) or {}
    except yaml.YAMLError as exc:
        raise GatewayValidationError(
            "Invalid YAML in gateway config.",
            details={"path": str(config_path), "error": str(exc)},
        ) from exc

    if not isinstance(data, dict):
        raise GatewayValidationError(
            "Gateway config root must be a mapping.",
            details={"path": str(config_path)},
        )

    try:
        return GatewayYamlConfig.model_validate(data)
    except ValidationError as exc:
        raise GatewayValidationError(
            "Gateway config validation failed.",
            details={"path": str(config_path), "errors": exc.errors()},
        ) from exc
