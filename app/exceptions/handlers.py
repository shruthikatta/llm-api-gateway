from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.exceptions.base import GatewayError
from app.exceptions.gateway import InternalGatewayError, ValidationError

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(GatewayError)
    async def gateway_exception_handler(
        request: Request,
        exc: GatewayError,
    ) -> JSONResponse:
        headers = {}
        if exc.status_code == 401:
            headers["WWW-Authenticate"] = "Bearer"
        retry_after = getattr(exc, "retry_after", None)
        if retry_after is not None:
            headers["Retry-After"] = str(retry_after)

        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.to_dict()},
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        error = ValidationError(
            "Request validation failed.",
            details=exc.errors(),
        )
        return JSONResponse(
            status_code=error.status_code,
            content={"error": error.to_dict()},
        )

    @app.exception_handler(Exception)
    async def unknown_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        error = InternalGatewayError("Internal server error")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": error.to_dict()},
        )
