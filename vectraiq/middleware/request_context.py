"""
Request context middleware.

Injects a unique request ID into every request, measures end-to-end
latency, and emits a structured access log on response.

The request ID is set as:
- A response header: X-Request-ID
- A contextvars variable accessible via logging_config.get_request_id()
"""

from __future__ import annotations

import time
import uuid

from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from vectraiq.logging_config import set_request_id


class RequestContextMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that manages request context and access logging."""

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        # Generate or propagate request ID
        rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = set_request_id(rid)

        t0 = time.perf_counter()
        status_code = 500
        try:
            response: Response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception as exc:
            logger.exception(
                "Unhandled exception | rid={} method={} path={}", rid, request.method, request.url.path
            )
            raise exc from None
        finally:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            _log_access(request, rid, status_code, elapsed_ms)
            from contextvars import copy_context  # noqa: F401  (token reset)
            try:
                from vectraiq.logging_config import request_id_var
                request_id_var.reset(token)
            except Exception:
                pass


def _log_access(
    request: Request, rid: str, status_code: int, elapsed_ms: float
) -> None:
    level = "INFO"
    if status_code >= 500:
        level = "ERROR"
    elif status_code >= 400:
        level = "WARNING"

    logger.log(
        level,
        "Access | rid={} method={} path={} status={} latency={:.1f}ms client={}",
        rid,
        request.method,
        request.url.path,
        status_code,
        elapsed_ms,
        request.client.host if request.client else "unknown",
    )
