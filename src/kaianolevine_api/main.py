from __future__ import annotations

from typing import Any

import sentry_sdk
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sentry_sdk.integrations.fastapi import FastApiIntegration

from .config import get_settings
from .routers import (
    catalog,
    contact,
    evaluations,
    flags,
    ingest,
    live_plays,
    resume,
    sets,
    spotify,
    stats,
    tracks,
    webhook,
)
from .schemas import ErrorDetail, ErrorEnvelope


def _build_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(title="kaianolevine-api", version=settings.API_VERSION)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["*"],
    )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
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
                    details=[
                        {
                            "loc": str(e.get("loc")),
                            "msg": e.get("msg"),
                            "type": e.get("type"),
                        }
                        for e in errors
                    ],
                )
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
        if isinstance(exc, HTTPException):
            detail: Any = exc.detail
            if isinstance(detail, dict) and "code" in detail and "message" in detail:
                payload = ErrorEnvelope(
                    error=ErrorDetail(
                        code=detail["code"],
                        message=detail["message"],
                        details=detail.get("details"),
                    )
                ).model_dump()
            else:
                payload = ErrorEnvelope(
                    error=ErrorDetail(code="http_error", message=str(exc.detail))
                ).model_dump()
            return JSONResponse(status_code=exc.status_code, content=payload)

        return JSONResponse(
            status_code=500,
            content=ErrorEnvelope(
                error=ErrorDetail(
                    code="internal_error", message="Unhandled server error"
                )
            ).model_dump(),
        )

    # HTTPException handler needs to be imported after ErrorEnvelope exists.
    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
        detail: Any = exc.detail
        if isinstance(detail, dict) and "code" in detail and "message" in detail:
            payload = ErrorEnvelope(
                error=ErrorDetail(
                    code=detail["code"],
                    message=detail["message"],
                    details=detail.get("details"),
                )
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
    app.include_router(flags.router, prefix="/v1", tags=["flags"])
    app.include_router(stats.router, prefix="/v1", tags=["stats"])
    app.include_router(spotify.router, prefix="/v1", tags=["spotify"])
    app.include_router(ingest.router, prefix="/v1", tags=["ingest"])
    app.include_router(live_plays.router, prefix="/v1", tags=["live-plays"])
    app.include_router(webhook.router, prefix="/v1", tags=["webhook"])
    app.include_router(contact.router, prefix="/v1", tags=["contact"])
    app.include_router(resume.router, prefix="/v1", tags=["resume"])

    return app


app = _build_app()


@app.get(
    "/version",
    tags=["meta"],
    summary="API version",
    description="Returns the currently deployed package version.",
    response_model=dict,
)
async def version() -> dict:
    from importlib.metadata import version as pkg_version

    try:
        v = pkg_version("kaianolevine-api")
    except Exception:
        v = get_settings().API_VERSION
    return {"version": v}


@app.on_event("startup")
async def _startup() -> None:
    settings = get_settings()
    if not settings.SENTRY_DSN:
        return

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        integrations=[FastApiIntegration()],
        environment=settings.ENVIRONMENT,
        traces_sample_rate=1.0,
    )
