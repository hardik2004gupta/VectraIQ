"""
Observability hooks for VectraIQ.

Provides clean extension points for:
- Request timing
- AI provider call metrics (latency, token usage)
- Vector search latency
- Cache hit/miss recording
- SQL execution timing

Langfuse integration is enabled when LANGFUSE_SECRET_KEY and
LANGFUSE_PUBLIC_KEY are set in the environment. Set LANGFUSE_ENABLED=false
to disable explicitly even if credentials are present.

OpenTelemetry tracing is enabled when OTEL_EXPORTER_OTLP_ENDPOINT is set.
Set OTEL_ENABLED=false to disable explicitly.
"""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Generator

from loguru import logger

# ── Feature flags ─────────────────────────────────────────────────────────────

_LANGFUSE_ENABLED: bool = (
    os.getenv("LANGFUSE_ENABLED", "true").lower() not in ("false", "0", "no")
    and bool(os.getenv("LANGFUSE_SECRET_KEY"))
    and bool(os.getenv("LANGFUSE_PUBLIC_KEY"))
)

_OTEL_ENABLED: bool = (
    os.getenv("OTEL_ENABLED", "true").lower() not in ("false", "0", "no")
    and bool(os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"))
)


# ── Langfuse client (lazy-initialized) ───────────────────────────────────────

_langfuse_client: Any = None


def _get_langfuse() -> Any:
    """Return a Langfuse client, initializing it on first call."""
    global _langfuse_client
    if not _LANGFUSE_ENABLED:
        return None
    if _langfuse_client is None:
        try:
            from langfuse import Langfuse
            _langfuse_client = Langfuse(
                secret_key=os.getenv("LANGFUSE_SECRET_KEY", ""),
                public_key=os.getenv("LANGFUSE_PUBLIC_KEY", ""),
                host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
            )
            logger.info("Langfuse tracing enabled")
        except ImportError:
            logger.warning(
                "LANGFUSE_SECRET_KEY is set but langfuse package is not installed. "
                "Run: uv add langfuse"
            )
            return None
        except Exception as exc:
            logger.warning("Langfuse init failed: {}. Tracing disabled.", exc)
            return None
    return _langfuse_client


# ── Metric dataclasses ────────────────────────────────────────────────────────

@dataclass
class AICallMetrics:
    """Captured metrics from a single LLM or embedding call."""
    provider: str = "openai"
    model: str = ""
    operation: str = ""          # "generate" | "embed" | "rerank"
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    cache_hit: bool = False
    error: str | None = None


@dataclass
class SearchMetrics:
    """Metrics from a single vector/hybrid search call."""
    mode: str = "dense"          # "dense" | "sparse" | "hybrid"
    num_results: int = 0
    latency_ms: float = 0.0
    reranked: bool = False
    hyde_used: bool = False
    crag_used: bool = False
    crag_label: str = ""


@dataclass
class RequestMetrics:
    """Aggregated metrics for a single HTTP request."""
    request_id: str = ""
    endpoint: str = ""
    method: str = ""
    user_id: str = ""
    intent: str = ""
    total_latency_ms: float = 0.0
    ai_calls: list[AICallMetrics] = field(default_factory=list)
    search: SearchMetrics | None = None
    cache_hit: bool = False
    error: str | None = None
    status_code: int = 200


# ── Recording functions (currently log-only; replace to send to Langfuse / OTEL) ──

def record_ai_call(metrics: AICallMetrics) -> None:
    """Record an AI provider call. Logs locally and optionally sends to Langfuse."""
    logger.debug(
        "AI call | provider={} model={} op={} tokens={} latency={:.1f}ms cache={}",
        metrics.provider,
        metrics.model,
        metrics.operation,
        metrics.total_tokens,
        metrics.latency_ms,
        metrics.cache_hit,
    )

    lf = _get_langfuse()
    if lf is not None:
        try:
            lf.generation(
                name=f"{metrics.provider}/{metrics.operation}",
                model=metrics.model,
                usage={
                    "prompt_tokens": metrics.prompt_tokens,
                    "completion_tokens": metrics.completion_tokens,
                    "total_tokens": metrics.total_tokens,
                },
                metadata={
                    "latency_ms": metrics.latency_ms,
                    "cache_hit": metrics.cache_hit,
                    "error": metrics.error,
                },
            )
        except Exception as exc:
            logger.debug("Langfuse generation record failed: {}", exc)


def record_search(metrics: SearchMetrics) -> None:
    """Record a retrieval call. Logs locally and optionally sends to Langfuse."""
    logger.debug(
        "Search | mode={} results={} latency={:.1f}ms rerank={} hyde={} crag={} label={}",
        metrics.mode,
        metrics.num_results,
        metrics.latency_ms,
        metrics.reranked,
        metrics.hyde_used,
        metrics.crag_used,
        metrics.crag_label,
    )


def record_request(metrics: RequestMetrics) -> None:
    """Record per-request summary. Logs locally and optionally sends to Langfuse."""
    logger.info(
        "Request done | rid={} endpoint={} user={} intent={} latency={:.1f}ms "
        "cache={} status={}{}",
        metrics.request_id,
        metrics.endpoint,
        metrics.user_id,
        metrics.intent,
        metrics.total_latency_ms,
        metrics.cache_hit,
        metrics.status_code,
        f" error={metrics.error}" if metrics.error else "",
    )

    lf = _get_langfuse()
    if lf is not None:
        try:
            lf.trace(
                name="vectraiq-request",
                metadata={
                    "request_id": metrics.request_id,
                    "endpoint": metrics.endpoint,
                    "method": metrics.method,
                    "user_id": metrics.user_id,
                    "intent": metrics.intent,
                    "latency_ms": metrics.total_latency_ms,
                    "cache_hit": metrics.cache_hit,
                    "status_code": metrics.status_code,
                    "error": metrics.error,
                },
            )
        except Exception as exc:
            logger.debug("Langfuse trace record failed: {}", exc)


# ── Context managers ──────────────────────────────────────────────────────────

@contextmanager
def timed_ai_call(
    operation: str,
    model: str = "",
    provider: str = "openai",
) -> Generator[AICallMetrics, None, None]:
    """Context manager that times an AI call and records it on exit.

    Usage::

        with timed_ai_call("generate", model="gpt-4o") as m:
            result = openai_client.chat.completions.create(...)
            m.prompt_tokens = result.usage.prompt_tokens
            m.total_tokens = result.usage.total_tokens
    """
    m = AICallMetrics(provider=provider, model=model, operation=operation)
    t0 = time.perf_counter()
    try:
        yield m
    except Exception as exc:
        m.error = str(exc)
        raise
    finally:
        m.latency_ms = (time.perf_counter() - t0) * 1000
        record_ai_call(m)


@contextmanager
def timed_search(mode: str = "dense") -> Generator[SearchMetrics, None, None]:
    """Context manager that times a vector search call and records it on exit."""
    m = SearchMetrics(mode=mode)
    t0 = time.perf_counter()
    try:
        yield m
    except Exception as exc:
        logger.error("Search failed mode={}: {}", mode, exc)
        raise
    finally:
        m.latency_ms = (time.perf_counter() - t0) * 1000
        record_search(m)


def timer() -> "_Timer":
    """Return a simple wall-clock timer."""
    return _Timer()


class _Timer:
    def __init__(self) -> None:
        self._start = time.perf_counter()

    def elapsed_ms(self) -> float:
        return (time.perf_counter() - self._start) * 1000
