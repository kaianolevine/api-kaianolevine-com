from __future__ import annotations

from contextlib import asynccontextmanager
from importlib.metadata import version as pkg_version
from typing import Any

import sentry_sdk
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from mini_app_polis.logger import (
    LOG_FAILURE,
    LOG_START,
    LOG_WARNING,
    get_logger,
    with_log_prefix,
)
from sentry_sdk.integrations.fastapi import FastApiIntegration

from .config import get_settings
from .routers import (
    catalog,
    contact,
    evaluations,
    flags,
    identity_debug,
    ingest,
    live_plays,
    notifications,
    resume,
    sets,
    spotify,
    stats,
    tracks,
    wcs_admin,
    wcs_auth,
    wcs_notes,
    wcs_qa,
    wcs_sources,
    wcs_wiki,
    webhook,
)
from .schemas import ErrorDetail, ErrorEnvelope

logger = get_logger()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Initialize and tear down process-level app resources."""
    settings = get_settings()
    if settings.SENTRY_DSN_API:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN_API,
            integrations=[FastApiIntegration()],
            environment=settings.ENVIRONMENT,
            traces_sample_rate=1.0,
        )
        logger.info(
            with_log_prefix(
                LOG_START,
                f"kaianolevine-api starting (env={settings.ENVIRONMENT}, sentry=on)",
            )
        )
    else:
        logger.info(
            with_log_prefix(
                LOG_START,
                f"kaianolevine-api starting (env={settings.ENVIRONMENT}, sentry=off)",
            )
        )
    await _reconcile_identity_registry()

    yield
    logger.info(with_log_prefix(LOG_WARNING, "kaianolevine-api shutting down"))


async def _reconcile_identity_registry() -> None:
    """Apply the declared machine principals (identity_registry.MACHINES).

    Runs on every boot so a deploy is what applies a declaration change.
    Failures are logged and swallowed: reconciliation must never take the
    service down, and failing to grant is already fail-closed — an ungranted
    principal is denied by the ordinary authorization path, not let through.
    """
    try:
        from sqlalchemy.ext.asyncio import async_sessionmaker

        from .database import get_engine
        from .identity_registry import reconcile

        maker = async_sessionmaker(get_engine(), expire_on_commit=False)
        async with maker() as session:
            result = await reconcile(session)
        if any(result.values()):
            logger.info(
                with_log_prefix(
                    LOG_START,
                    "identity registry reconciled "
                    f"created={result['created']} granted={result['granted']} "
                    f"revoked={result['revoked']}",
                )
            )
    except Exception as exc:  # noqa: BLE001 - see docstring
        logger.warning(
            with_log_prefix(
                LOG_WARNING, f"identity registry reconciliation failed: {exc!r}"
            )
        )


def _build_app() -> FastAPI:
    settings = get_settings()

    try:
        api_version = pkg_version("kaianolevine-api")
    except Exception:
        api_version = settings.API_VERSION

    app = FastAPI(title="kaianolevine-api", version=api_version, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["*"],
    )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Render request validation failures as the standard error envelope."""
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
        """Render unhandled exceptions as a generic internal error envelope."""
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

        logger.exception(
            with_log_prefix(LOG_FAILURE, f"unhandled exception: {type(exc).__name__}")
        )
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
        """Render HTTPException responses using the standard error envelope."""
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
    app.include_router(identity_debug.router, prefix="/v1", tags=["identity"])
    app.include_router(stats.router, prefix="/v1", tags=["stats"])
    app.include_router(spotify.router, prefix="/v1", tags=["spotify"])
    app.include_router(ingest.router, prefix="/v1", tags=["ingest"])
    app.include_router(live_plays.router, prefix="/v1", tags=["live-plays"])
    app.include_router(webhook.router, prefix="/v1", tags=["webhook"])
    app.include_router(notifications.router, prefix="/v1", tags=["notifications"])
    app.include_router(contact.router, prefix="/v1", tags=["contact"])
    app.include_router(resume.router, prefix="/v1", tags=["resume"])
    app.include_router(wcs_notes.router, prefix="/v1", tags=["wcs"])
    app.include_router(wcs_sources.router, prefix="/v1", tags=["wcs"])
    app.include_router(wcs_wiki.router, prefix="/v1", tags=["wcs"])
    app.include_router(wcs_auth.router, prefix="/v1", tags=["wcs"])
    app.include_router(wcs_qa.router, prefix="/v1", tags=["wcs"])
    app.include_router(wcs_admin.router, prefix="/v1", tags=["wcs-admin"])

    return app


app = _build_app()


@app.get(
    "/health",
    tags=["meta"],
    summary="Liveness probe",
    description=(
        "Returns {'status': 'ok'} with no auth and no database queries. "
        "Intentionally public — used by load balancers and uptime monitors."
    ),
    response_model=dict,
)
async def health() -> dict:
    """Liveness probe. Intentionally public — no auth, no DB access."""
    return {"status": "ok"}


@app.get(
    "/version",
    tags=["meta"],
    summary="API version",
    description=(
        "Returns the currently deployed package version. Intentionally public "
        "and unversioned: the endpoint reports which API version is running, "
        "so it must be reachable at a stable version-independent path with "
        "no auth."
    ),
    response_model=dict,
)
async def version() -> dict:
    """Return the currently deployed package version. Intentionally public."""
    return {"version": app.version}


@app.get(
    "/",
    include_in_schema=False,
    summary="Root redirect to interactive docs",
    description=(
        "Redirects to /docs (Swagger UI). Intentionally public — the "
        "redirect target is itself publicly browsable documentation."
    ),
    response_model=None,
)
async def root() -> RedirectResponse:
    """Redirect to the Swagger UI at /docs. Intentionally public."""
    return RedirectResponse(url="/docs")
