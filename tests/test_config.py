from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.config.loader import load_gateway_config
from app.config.store import ConfigStore, reset_config_store
from app.exceptions.gateway import ValidationError


@pytest.fixture(autouse=True)
def _reset_store():
    reset_config_store()
    yield
    reset_config_store()


def test_load_default_gateway_config():
    config = load_gateway_config()
    assert config.gateway.default_timeout_seconds > 0
    assert config.provider_enabled("openai")
    assert config.provider_enabled("mock")
    assert any(rule.prefix == "gpt" for rule in config.routing.heuristics)
    assert config.rate_limit.default_requests_per_minute > 0
    assert config.budget.default_daily_budget_usd >= 0
    assert config.resilience.max_retries >= 0


def test_invalid_yaml_rejected(tmp_path: Path):
    path = tmp_path / "bad.yaml"
    path.write_text("logging: [\n  - broken", encoding="utf-8")

    with pytest.raises(ValidationError):
        load_gateway_config(path)


def test_invalid_schema_rejected(tmp_path: Path):
    path = tmp_path / "bad-schema.yaml"
    path.write_text(
        yaml.safe_dump({"gateway": {"default_timeout_seconds": -1}}),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        load_gateway_config(path)


def test_hot_reload_keeps_previous_on_invalid(tmp_path: Path):
    path = tmp_path / "gateway.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "gateway": {"hot_reload": True, "default_timeout_seconds": 30},
                "providers": {"mock": {"enabled": True}},
            }
        ),
        encoding="utf-8",
    )

    store = ConfigStore(path)
    assert store.get().gateway.default_timeout_seconds == 30

    path.write_text("logging: [\n", encoding="utf-8")

    with pytest.raises(ValidationError):
        store.reload(force=True)

    assert store.get().gateway.default_timeout_seconds == 30


def test_hot_reload_applies_valid_update(tmp_path: Path):
    path = tmp_path / "gateway.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "gateway": {"default_timeout_seconds": 30},
                "providers": {"mock": {"enabled": True}},
            }
        ),
        encoding="utf-8",
    )
    store = ConfigStore(path)

    path.write_text(
        yaml.safe_dump(
            {
                "gateway": {"default_timeout_seconds": 45},
                "providers": {"mock": {"enabled": True}},
            }
        ),
        encoding="utf-8",
    )
    assert store.reload(force=True) is True
    assert store.get().gateway.default_timeout_seconds == 45
