"""
Admin / operational endpoints.

GET  /admin/health        — dependency health check (public)
GET  /admin/cache/stats   — per-tier cache statistics (admin only)
POST /admin/cache/clear   — clear in-memory cache (admin only)

Health check is intentionally unauthenticated so load balancers and
container orchestrators can poll it without credentials.
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, status
from loguru import logger

from vectraiq.cache.query_cache import query_cache
from vectraiq.config import settings
from vectraiq.middleware.auth import User, require_admin
from vectraiq.models import CacheStatsResponse, CacheTierStats, ServiceHealth

router = APIRouter(tags=["admin"])


# ── Health probe helpers ──────────────────────────────────────────────────────

async def _ping_postgres() -> bool:
    try:
        import psycopg2
        conn = psycopg2.connect(settings.database_url, connect_timeout=2)
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        return True
    except Exception as exc:
        logger.debug("Postgres health check failed: {}", exc)
        return False


async def _ping_qdrant() -> bool:
    try:
        from qdrant_client import QdrantClient
        client = QdrantClient(url=settings.qdrant_url, timeout=2)
        client.get_collections()
        return True
    except Exception as exc:
        logger.debug("Qdrant health check failed: {}", exc)
        return False


async def _ping_redis() -> bool:
    if not settings.redis_enabled:
        return False
    try:
        from upstash_redis import Redis
        redis = Redis(url=settings.upstash_redis_url, token=settings.upstash_redis_token)
        redis.ping()
        return True
    except Exception as exc:
        logger.debug("Redis health check failed: {}", exc)
        return False


async def _ping_openai() -> bool:
    if not settings.openai_api_key:
        return False
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        await client.models.list()
        return True
    except Exception as exc:
        logger.debug("OpenAI health check failed: {}", exc)
        return False


async def _ping_tavily() -> bool:
    if not settings.tavily_enabled:
        return True   # Not configured → not expected → not "down"
    try:
        from vectraiq.ai.web_search import search_web
        search_web("health check")
        return True
    except Exception as exc:
        logger.debug("Tavily health check failed: {}", exc)
        return False


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get(
    "/admin/health",
    response_model=ServiceHealth,
    status_code=status.HTTP_200_OK,
    summary="Check health of all dependencies",
    description="Parallel-probes Postgres, Qdrant, Redis, OpenAI, and Tavily. No authentication required.",
)
async def health_check() -> ServiceHealth:
    results: tuple[Any, ...] = await asyncio.gather(
        _ping_postgres(),
        _ping_qdrant(),
        _ping_redis(),
        _ping_openai(),
        _ping_tavily(),
        return_exceptions=True,
    )

    def _ok(r: Any) -> bool:
        return bool(r) and not isinstance(r, Exception)

    postgres_ok = _ok(results[0])
    qdrant_ok = _ok(results[1])
    redis_ok = _ok(results[2])
    openai_ok = _ok(results[3])
    tavily_ok = _ok(results[4])

    all_critical_ok = all([postgres_ok, qdrant_ok, openai_ok])
    overall = "ok" if all_critical_ok else "degraded"

    health = ServiceHealth(
        status=overall,
        qdrant=qdrant_ok,
        postgres=postgres_ok,
        redis=redis_ok,
        openai=openai_ok,
        tavily=tavily_ok,
    )

    # Return 503 when any critical dependency is down so load balancers and
    # Kubernetes liveness probes correctly detect a degraded backend.
    http_status = status.HTTP_200_OK if all_critical_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=http_status, content=health.model_dump())


@router.get(
    "/admin/cache/stats",
    response_model=CacheStatsResponse,
    summary="Per-tier cache hit/miss statistics",
    description="Returns hit rate, miss count, and set count for each of the five cache tiers. Admin only.",
)
async def cache_stats(user: User = Depends(require_admin)) -> CacheStatsResponse:
    raw = query_cache.stats()

    def _tier(name: str) -> CacheTierStats:
        t = raw.get(name, {})
        return CacheTierStats(
            hits=int(t.get("hits", 0)),
            misses=int(t.get("misses", 0)),
            sets=int(t.get("sets", 0)),
            hit_rate=float(t.get("hit_rate", 0.0)),
        )

    return CacheStatsResponse(
        embedding=_tier("embedding"),
        rag=_tier("rag_answer"),
        sql_gen=_tier("sql_gen"),
        sql_result=_tier("sql_result"),
        intent_router=_tier("intent"),
    )


@router.post(
    "/admin/cache/clear",
    status_code=status.HTTP_200_OK,
    summary="Clear the in-memory cache and reset statistics",
    description=(
        "Clears all in-memory cache entries and resets hit/miss counters. "
        "Remote Redis entries are not cleared (Upstash HTTP API limitation). "
        "Admin only."
    ),
)
async def cache_clear(user: User = Depends(require_admin)) -> dict[str, Any]:
    cleared = query_cache.clear()
    logger.info("Cache cleared by admin | user={} cleared={}", user.username, cleared)
    return {"status": "ok", "cleared": cleared}
