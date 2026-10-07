"""SMAReX API entrypoint.

Run with:  uvicorn app.main:app --reload
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import SMAReXError
from app.core.logging import RequestContextMiddleware, configure_logging, get_logger
from app.db.session import dispose_engine, get_session_factory

settings = get_settings()
configure_logging(settings.log_level, settings.log_json)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Starting %s v%s (%s)", settings.app_name, settings.app_version, settings.environment
    )
    yield
    await dispose_engine()
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Backend for SMAReX, the Smart Academic Resource Exchange. "
        "Handles IIUM Live authentication, the VirusTotal-validated PDF upload "
        "pipeline, AI summarisation, and resource engagement."
    ),
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url="/redoc" if settings.environment != "production" else None,
    openapi_url="/openapi.json" if settings.environment != "production" else None,
    lifespan=lifespan,
)

app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)
# ---------------------------------------------------------------------------
# Error handling: one consistent envelope for every failure.
# ---------------------------------------------------------------------------
@app.exception_handler(SMAReXError)
async def handle_domain_error(request: Request, exc: SMAReXError):
    request_id = getattr(request.state, "request_id", None)
    if exc.status_code >= 500:
        logger.error("%s: %s", exc.code, exc.message)
    else:
        logger.info("%s -> %d (%s)", exc.code, exc.status_code, exc.message)
    return JSONResponse(status_code=exc.status_code, content=exc.to_payload(request_id))


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, exc: RequestValidationError):
    """Turn pydantic errors into a readable list of field problems."""
    request_id = getattr(request.state, "request_id", None)
    fields = []
    for error in exc.errors():
        location = [str(p) for p in error.get("loc", []) if p not in ("body", "query")]
        fields.append(
            {
                "field": ".".join(location) or "request",
                "message": error.get("msg", "Invalid value"),
            }
        )
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "Please check the highlighted fields and try again.",
                "details": {"fields": fields},
                "request_id": request_id,
            }
        },
    )


@app.exception_handler(Exception)
async def handle_unexpected(request: Request, exc: Exception):
    """Last resort. Never leaks internals to the browser."""
    request_id = getattr(request.state, "request_id", None)
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_error",
                "message": "Something went wrong on our end. Please try again.",
                "request_id": request_id,
            }
        },
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/health", tags=["system"])
async def health():
    """Liveness plus a database round-trip. Safe to call unauthenticated.

    Returns a ``hint`` when the database is unreachable so the cause is
    obvious from the browser without opening the server logs.
    """
    checks: dict[str, str] = {}
    hint: str | None = None

    try:
        factory = get_session_factory()
        async with factory() as session:
            await session.execute(text("select 1"))
        checks["database"] = "ok"
    except Exception as exc:
        name = type(exc).__name__
        logger.error("Health check: database unreachable (%s: %s)", name, exc)

        if isinstance(exc, ModuleNotFoundError):
            checks["database"] = "driver missing"
            hint = "Install the database driver: pip install -r requirements.txt"
        else:
            checks["database"] = "unavailable"
            detail = str(exc)
            if "timed out" in detail.lower() or "timeout" in detail.lower():
                hint = (
                    "Connection timed out. The direct connection (port 5432) needs "
                    "IPv6. Use the transaction pooler on port 6543 instead."
                )
            elif "password authentication failed" in detail.lower():
                hint = "Check the password in DATABASE_URL."
            elif "does not exist" in detail.lower():
                hint = "Apply the migrations in supabase/migrations/."
            else:
                hint = "Check DATABASE_URL in backend/.env."

    return {
        "status": "ok" if checks.get("database") == "ok" else "degraded",
        "version": settings.app_version,
        "environment": settings.environment,
        "checks": checks,
        **({"hint": hint} if hint else {}),
    }


@app.get("/", tags=["system"])
async def root():
    return {"name": settings.app_name, "version": settings.app_version, "docs": "/docs"}