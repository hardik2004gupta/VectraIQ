"""
Structured logging configuration for VectraIQ.

Uses loguru with:
- JSON mode in production (LOG_JSON=true)
- Human-readable format in development
- Request-ID context propagation via contextvars
- Intercept of stdlib logging so third-party libs (uvicorn, fastapi) route through loguru
"""

from __future__ import annotations

import contextvars
import logging
import sys
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    pass

# ── Request-ID context ────────────────────────────────────────────────────────

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)


def get_request_id() -> str:
    return request_id_var.get()


def set_request_id(rid: str) -> contextvars.Token[str]:
    return request_id_var.set(rid)


# ── Stdlib → loguru bridge ────────────────────────────────────────────────────

class _StdlibHandler(logging.Handler):
    """Redirect all stdlib logging records into loguru."""

    _map = {
        logging.CRITICAL: "CRITICAL",
        logging.ERROR: "ERROR",
        logging.WARNING: "WARNING",
        logging.INFO: "INFO",
        logging.DEBUG: "DEBUG",
    }

    def emit(self, record: logging.LogRecord) -> None:
        level = self._map.get(record.levelno, "DEBUG")
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back  # type: ignore[assignment]
            depth += 1
        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def _json_format(record: "logging.LogRecord") -> str:  # noqa: F821  (loguru Record)
    import json
    payload = {
        "ts": record["time"].isoformat(),  # type: ignore[index]
        "level": record["level"].name,  # type: ignore[index]
        "logger": record["name"],  # type: ignore[index]
        "request_id": get_request_id(),
        "message": record["message"],  # type: ignore[index]
    }
    if record["exception"]:  # type: ignore[index]
        payload["exception"] = str(record["exception"])  # type: ignore[index]
    return json.dumps(payload) + "\n"


_DEV_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "rid=<yellow>{extra[request_id]}</yellow> — "
    "<level>{message}</level>"
)


def configure(log_level: str = "INFO", log_json: bool = False) -> None:
    """Configure loguru. Call once at application startup."""
    logger.remove()

    if log_json:
        logger.add(
            sys.stdout,
            level=log_level,
            format=_json_format,
            colorize=False,
            enqueue=True,
        )
    else:
        logger.add(
            sys.stdout,
            level=log_level,
            format=_DEV_FORMAT,
            colorize=True,
            enqueue=True,
        )

    # Add request_id to every record via patcher
    logger.configure(patcher=lambda r: r["extra"].update(request_id=get_request_id()))

    # Redirect stdlib logging
    logging.basicConfig(handlers=[_StdlibHandler()], level=0, force=True)
    for lib in ("uvicorn", "uvicorn.access", "uvicorn.error", "fastapi", "httpx"):
        logging.getLogger(lib).handlers = []
        logging.getLogger(lib).propagate = True
