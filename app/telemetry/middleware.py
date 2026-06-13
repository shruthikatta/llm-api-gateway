from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.telemetry.metrics import REQUEST_LATENCY_SECONDS, REQUESTS_TOTAL


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Record HTTP request counts and latency for Prometheus."""

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path == "/metrics":
            return await call_next(request)

        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            elapsed = time.perf_counter() - started
            endpoint = request.url.path
            REQUESTS_TOTAL.labels(
                endpoint=endpoint,
                status=str(status_code),
                provider="gateway",
            ).inc()
            REQUEST_LATENCY_SECONDS.labels(
                provider="gateway",
                model="http",
            ).observe(elapsed)
