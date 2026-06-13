from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.telemetry.metrics import (
    FAILOVER_TOTAL,
    REQUESTS_TOTAL,
    metrics_payload,
    record_circuit_state,
)


def test_metrics_endpoint_returns_prometheus_format():
    client = TestClient(app)
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "gateway_requests_total" in response.text
    assert "text/plain" in response.headers["content-type"]


def test_record_circuit_state_updates_gauge():
    record_circuit_state("mock", "open")
    payload = metrics_payload().decode()
    assert "gateway_circuit_breaker_state" in payload


def test_failover_counter_increments():
    before = FAILOVER_TOTAL.labels(from_provider="openai", to_provider="mock")._value.get()
    FAILOVER_TOTAL.labels(from_provider="openai", to_provider="mock").inc()
    after = FAILOVER_TOTAL.labels(from_provider="openai", to_provider="mock")._value.get()
    assert after > before


def test_dashboard_index_served():
    client = TestClient(app)
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "LLM API Gateway" in response.text


def test_root_lists_dashboard_and_metrics():
    client = TestClient(app)
    response = client.get("/")
    body = response.json()
    assert body["dashboard"] == "/dashboard"
    assert body["metrics"] == "/metrics"
