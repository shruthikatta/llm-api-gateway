from __future__ import annotations

from fastapi import APIRouter, Response

from app.telemetry.metrics import metrics_payload

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
def prometheus_metrics() -> Response:
    """Prometheus scrape endpoint."""
    return Response(
        content=metrics_payload(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
