"""
Sliding-window rate limiter backed by Upstash Redis.

Falls back to in-memory permissive mode when Redis is unavailable —
the application stays up with a warning rather than returning 500s.

Two flavours:
- is_allowed_ip(ip, route, limit, window)  — for auth endpoints (per-IP)
- is_allowed_user(user_id, limit, window)  — for query endpoints (per-user)

Both return (allowed: bool, remaining: int, current_count: int).
"""

from __future__ import annotations

import time

from loguru import logger

from vectraiq.config import settings


class RateLimiter:
    """Sliding-window rate limiter using a Redis sorted-set per key."""

    def __init__(self, max_requests: int, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    def is_allowed(self, key: str) -> tuple[bool, int, int]:
        """Return (allowed, remaining, current_count)."""
        try:
            client = _get_redis_client()
            now = time.time()
            window_start = now - self.window_seconds

            pipe = client.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zadd(key, {str(now): now})
            pipe.zcard(key)
            pipe.expire(key, self.window_seconds)
            results = pipe.exec()

            request_count: int = results[2]  # type: ignore[assignment]
            remaining = max(0, self.max_requests - request_count)
            return request_count <= self.max_requests, remaining, request_count
        except Exception:
            logger.warning("Redis unavailable for rate limiting; allowing request")
            return True, self.max_requests, 0


# ── Lazy Redis singleton ──────────────────────────────────────────────────────

_redis_client = None


def _get_redis_client():
    global _redis_client
    if _redis_client is None:
        from upstash_redis import Redis
        _redis_client = Redis(
            url=settings.upstash_redis_url,
            token=settings.upstash_redis_token,
        )
    return _redis_client


# ── Module-level limiter singletons (avoids per-call instantiation) ───────────

_user_limiter = RateLimiter(
    max_requests=settings.rate_limit_requests,
    window_seconds=settings.rate_limit_window_seconds,
)

# Auth limiters are keyed per-route with custom limits passed at call time.
# We create them lazily using the settings from config so they respect .env.


def is_allowed_ip(ip: str, route: str, limit: int, window_seconds: int) -> tuple[bool, int, int]:
    """Rate-limit by client IP (used for auth endpoints)."""
    limiter = RateLimiter(max_requests=limit, window_seconds=window_seconds)
    key = f"rate_limit:ip:{ip}:{route}"
    return limiter.is_allowed(key)


def is_allowed_user(
    user_id: str,
    limit: int = settings.rate_limit_requests,
    window_seconds: int = settings.rate_limit_window_seconds,
) -> tuple[bool, int, int]:
    """Rate-limit by authenticated user ID (used for query endpoints)."""
    # Use module-level singleton only when limit/window match global settings
    if limit == settings.rate_limit_requests and window_seconds == settings.rate_limit_window_seconds:
        key = f"rate_limit:user:{user_id}"
        return _user_limiter.is_allowed(key)
    # Custom limits: create an ephemeral limiter
    limiter = RateLimiter(max_requests=limit, window_seconds=window_seconds)
    key = f"rate_limit:user:{user_id}"
    return limiter.is_allowed(key)
