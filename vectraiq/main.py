"""
VectraIQ FastAPI application factory.

Middleware order (outermost → innermost):
  1. CORSMiddleware              — preflight handling
  2. RequestContextMiddleware    — request ID + timing + access log
  3. FastAPI routing layer       — auth, rate limiting, business logic

Exception handlers (registered globally):
  - VectraIQError subclasses → structured JSON with correct HTTP status
  - RequestValidationError   → 422 with field-level detail
  - HTTPException            → wrapped in error envelope
  - Exception                → 500 with opaque message
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from vectraiq.exceptions import VectraIQError
from vectraiq.logging_config import configure as configure_logging, get_request_id
from vectraiq.middleware.request_context import RequestContextMiddleware
from vectraiq.middleware.security_headers import SecurityHeadersMiddleware
from vectraiq.models import APIError, ErrorResponse
from vectraiq.config import settings


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown events."""
    # Configure structured logging first
    configure_logging(log_level=settings.log_level, log_json=settings.log_json)

    logger.info(
        "VectraIQ {} starting | env={} log_json={} log_level={}",
        app.version,
        "production" if settings.log_json else "development",
        settings.log_json,
        settings.log_level,
    )

    # Warn about missing critical config (don't crash — let ops fix in place)
    _warn_missing_config()

    yield  # application is running

    logger.info("VectraIQ shutting down")


def _warn_missing_config() -> None:
    missing = []
    if not settings.openai_api_key:
        missing.append("OPENAI_API_KEY")
    if not settings.jwt_secret:
        missing.append("JWT_SECRET")
    if not settings.upstash_redis_url:
        missing.append("UPSTASH_REDIS_URL (cache disabled, using in-memory fallback)")
    if missing:
        for item in missing:
            logger.warning("Config missing: {}", item)


# ── Exception handlers ────────────────────────────────────────────────────────

def _error_response(
    code: str,
    message: str,
    http_status: int,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    rid = get_request_id()
    body = ErrorResponse(
        error=APIError(code=code, message=message, details=details or {}),
        request_id=rid,
    )
    return JSONResponse(status_code=http_status, content=body.model_dump())


async def _vectraiq_error_handler(request: Request, exc: VectraIQError) -> JSONResponse:
    logger.warning(
        "Domain error | rid={} type={} message={}",
        get_request_id(),
        type(exc).__name__,
        exc.message,
    )
    return _error_response(
        code=exc.error_code,
        message=exc.message,
        http_status=exc.http_status,
    )


async def _http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    code_map = {
        400: "bad_request",
        401: "authentication_error",
        403: "authorization_error",
        404: "not_found",
        405: "method_not_allowed",
        409: "conflict",
        422: "validation_error",
        429: "rate_limit_exceeded",
        500: "internal_error",
        502: "upstream_error",
        503: "service_unavailable",
    }
    code = code_map.get(exc.status_code, "http_error")
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return _error_response(
        code=code,
        message=detail,
        http_status=exc.status_code,
    )


async def _validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    # Flatten Pydantic v2 error list into human-readable strings
    field_errors: list[str] = []
    for err in exc.errors():
        loc = " → ".join(str(part) for part in err.get("loc", []))
        msg = err.get("msg", "invalid")
        field_errors.append(f"{loc}: {msg}" if loc else msg)

    return _error_response(
        code="validation_error",
        message="Request validation failed",
        http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        details={"field_errors": field_errors},
    )


async def _generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "Unhandled exception | rid={} path={}", get_request_id(), request.url.path
    )
    return _error_response(
        code="internal_error",
        message="An unexpected error occurred. Please try again later.",
        http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


# ── Application factory ───────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title="VectraIQ",
        version="2.0.0",
        description=(
            "Production-grade AI Knowledge Platform — "
            "Kubernetes IT-Operations Copilot with Hybrid RAG, "
            "Text2SQL, Intelligent Routing, and Enterprise Security."
        ),
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        openapi_tags=[
            {
                "name": "query",
                "description": "AI-powered question answering via RAG, Text2SQL, and Hybrid pipelines.",
            },
            {
                "name": "auth",
                "description": "User registration and authentication (JWT bearer tokens).",
            },
            {
                "name": "admin",
                "description": "Health checks, cache management, and operational endpoints. Requires admin role.",
            },
        ],
    )

    # ── Middleware (added last = executes outermost) ───────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.frontend_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)

    # ── Exception handlers ─────────────────────────────────────────────────────
    app.add_exception_handler(VectraIQError, _vectraiq_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(HTTPException, _http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _generic_error_handler)

    # ── Routers ────────────────────────────────────────────────────────────────
    from vectraiq.api import admin, auth, query
    app.include_router(query.router)
    app.include_router(auth.router)
    app.include_router(admin.router)

    return app


app = create_app()
