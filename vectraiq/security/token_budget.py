"""Per-user daily token budget tracked in Redis."""

import datetime
import logging

from vectraiq.config import settings

logger = logging.getLogger(__name__)

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


class TokenBudget:
    def __init__(self, max_tokens: int) -> None:
        self.max_tokens = max_tokens

    def _key(self, user_id: str) -> str:
        today = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d")
        return f"token_budget:{user_id}:{today}"

    def check_budget(self, user_id: str, estimated_tokens: int) -> tuple[bool, int]:
        try:
            client = _get_redis_client()
            key = self._key(user_id)
            used_str = client.get(key)
            used = int(used_str) if used_str is not None else 0
            remaining = self.max_tokens - used
            return estimated_tokens <= remaining, remaining
        except Exception:
            logger.warning("Redis unavailable for token budget check; allowing request")
            return True, self.max_tokens

    def consume(self, user_id: str, actual_tokens: int) -> dict:
        try:
            client = _get_redis_client()
            key = self._key(user_id)
            used = client.incrby(key, actual_tokens)

            ttl = client.ttl(key)
            if ttl == -1:
                now = datetime.datetime.now(datetime.UTC)
                midnight = (now + datetime.timedelta(days=1)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                client.expire(key, int((midnight - now).total_seconds()))

            remaining = max(0, self.max_tokens - used)
            return {
                "used": used,
                "limit": self.max_tokens,
                "remaining": remaining,
                "tokens_charged": actual_tokens,
            }
        except Exception:
            logger.warning("Redis unavailable for token budget consume; skipping")
            return {"used": 0, "limit": self.max_tokens, "remaining": self.max_tokens, "tokens_charged": actual_tokens}


_budget = TokenBudget(max_tokens=settings.max_tokens_per_user_daily)


def check_budget(user_id: str, estimated_tokens: int) -> tuple[bool, int]:
    return _budget.check_budget(user_id, estimated_tokens)


def consume_budget(user_id: str, actual_tokens: int) -> dict:
    return _budget.consume(user_id, actual_tokens)
