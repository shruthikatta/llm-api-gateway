from __future__ import annotations

import logging

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from app.config.schema import TelemetrySection

logger = logging.getLogger(__name__)

_provider: TracerProvider | None = None


def setup_telemetry(settings: TelemetrySection) -> TracerProvider | None:
    """
    Bootstrap OpenTelemetry tracing.

    Local default: console exporter.
    When otlp_endpoint is set, export via OTLP/HTTP.
    """
    global _provider

    if not settings.enabled:
        logger.info("OpenTelemetry disabled via configuration")
        return None

    if _provider is not None:
        return _provider

    resource = Resource.create({"service.name": settings.service_name})
    provider = TracerProvider(resource=resource)

    if settings.otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )

            exporter = OTLPSpanExporter(endpoint=settings.otlp_endpoint)
        except ImportError:
            logger.warning(
                "OTLP exporter unavailable; falling back to console span exporter"
            )
            exporter = ConsoleSpanExporter()
    else:
        exporter = ConsoleSpanExporter()

    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _provider = provider
    logger.info(
        "OpenTelemetry initialized service=%s exporter=%s",
        settings.service_name,
        type(exporter).__name__,
    )
    return provider


def instrument_fastapi(app) -> None:
    """Attach FastAPI auto-instrumentation when OTel is active."""
    if _provider is None:
        return
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
    except ImportError:
        logger.warning("opentelemetry-instrumentation-fastapi not installed")


def shutdown_telemetry() -> None:
    global _provider
    if _provider is not None:
        _provider.shutdown()
        _provider = None


def get_tracer(name: str = "ai-gateway"):
    return trace.get_tracer(name)
