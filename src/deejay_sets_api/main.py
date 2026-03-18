from __future__ import annotations

from typing import Any

import sentry_sdk
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sentry_sdk.integrations.fastapi import FastApiIntegration

from .config import get_settings
from .routers import catalog, evaluations, ingest, sets, stats, tracks
from .schemas import ErrorDetail, ErrorEnvelope


def _build_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(title="deejay-sets-api", version=settings.API_VERSION)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = exc.errors()
        first = errors[0] if errors else {}
        loc = first.get("loc")
        msg = first.get("msg", "validation error")
        return JSONResponse(
            status_code=422,
            content=ErrorEnvelope(
                error=ErrorDetail(
                    code="validation_error",
                    message=f"Validation error at {loc}: {msg}",
                )
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
        if isinstance(exc, HTTPException):
            detail: Any = exc.detail
            if isinstance(detail, dict) and "code" in detail and "message" in detail:
                payload = ErrorEnvelope(
                    error=ErrorDetail(code=detail["code"], message=detail["message"])
                ).model_dump()
            else:
                payload = ErrorEnvelope(
                    error=ErrorDetail(code="http_error", message=str(exc.detail))
                ).model_dump()
            return JSONResponse(status_code=exc.status_code, content=payload)

        return JSONResponse(
            status_code=500,
            content=ErrorEnvelope(
                error=ErrorDetail(code="internal_error", message="Unhandled server error")
            ).model_dump(),
        )

    # HTTPException handler needs to be imported after ErrorEnvelope exists.
    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
        detail: Any = exc.detail
        if isinstance(detail, dict) and "code" in detail and "message" in detail:
            payload = ErrorEnvelope(
                error=ErrorDetail(code=detail["code"], message=detail["message"])
            ).model_dump()
        else:
            payload = ErrorEnvelope(
                error=ErrorDetail(code="http_error", message=str(exc.detail))
            ).model_dump()
        return JSONResponse(status_code=exc.status_code, content=payload)

    # Routers (versioned under /v1)
    app.include_router(sets.router, prefix="/v1", tags=["sets"])
    app.include_router(tracks.router, prefix="/v1", tags=["tracks"])
    app.include_router(catalog.router, prefix="/v1", tags=["catalog"])
    app.include_router(evaluations.router, prefix="/v1", tags=["evaluations"])
    app.include_router(stats.router, prefix="/v1", tags=["stats"])
    app.include_router(ingest.router, prefix="/v1", tags=["ingest"])

    return app


app = _build_app()


@app.on_event("startup")
async def _startup() -> None:
    settings = get_settings()
    if not settings.SENTRY_DSN:
        return

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        integrations=[FastApiIntegration()],
        environment=settings.ENVIRONMENT,
    )
