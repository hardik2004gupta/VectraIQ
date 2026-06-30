"""
VectraIQ domain exception hierarchy.

All application-specific errors derive from VectraIQError so callers
can distinguish library errors from infrastructure / third-party errors
with a single except clause.
"""

from __future__ import annotations

from http import HTTPStatus


class VectraIQError(Exception):
    """Base exception for all VectraIQ errors."""

    http_status: int = HTTPStatus.INTERNAL_SERVER_ERROR
    error_code: str = "internal_error"

    def __init__(self, message: str = "An unexpected error occurred") -> None:
        super().__init__(message)
        self.message = message

    def __repr__(self) -> str:
        return f"{type(self).__name__}(message={self.message!r})"


# ── Authentication / Authorization ───────────────────────────────────────────

class AuthenticationError(VectraIQError):
    """Invalid or missing credentials."""
    http_status = HTTPStatus.UNAUTHORIZED
    error_code = "authentication_error"

    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__(message)


class AuthorizationError(VectraIQError):
    """Authenticated user lacks permission."""
    http_status = HTTPStatus.FORBIDDEN
    error_code = "authorization_error"

    def __init__(self, message: str = "Insufficient permissions") -> None:
        super().__init__(message)


class TokenExpiredError(AuthenticationError):
    """JWT has expired."""
    error_code = "token_expired"

    def __init__(self) -> None:
        super().__init__("Authentication token has expired")


# ── Rate Limiting ─────────────────────────────────────────────────────────────

class RateLimitError(VectraIQError):
    """Request rate limit exceeded."""
    http_status = HTTPStatus.TOO_MANY_REQUESTS
    error_code = "rate_limit_exceeded"

    def __init__(self, message: str = "Rate limit exceeded. Please retry later.") -> None:
        super().__init__(message)


class TokenBudgetError(VectraIQError):
    """Daily token budget exhausted."""
    http_status = HTTPStatus.TOO_MANY_REQUESTS
    error_code = "token_budget_exceeded"

    def __init__(self, remaining: int, required: int) -> None:
        super().__init__(
            f"Daily token budget exhausted. Required: {required}, remaining: {remaining}."
        )
        self.remaining = remaining
        self.required = required


# ── Input Validation / Security ───────────────────────────────────────────────

class InputValidationError(VectraIQError):
    """Request input failed validation."""
    http_status = HTTPStatus.BAD_REQUEST
    error_code = "input_validation_error"


class InjectionDetectedError(InputValidationError):
    """Prompt injection detected in input."""
    error_code = "injection_detected"

    def __init__(self, reason: str | None = None) -> None:
        msg = "Input contains potentially malicious content"
        if reason:
            msg = f"{msg}: {reason}"
        super().__init__(msg)


class ContentBlockedError(InputValidationError):
    """Content was blocked by moderation."""
    error_code = "content_blocked"

    def __init__(self, reason: str | None = None) -> None:
        msg = "Content blocked by moderation policy"
        if reason:
            msg = f"{msg}: {reason}"
        super().__init__(msg)


# ── AI / LLM ─────────────────────────────────────────────────────────────────

class AIProviderError(VectraIQError):
    """LLM provider returned an error."""
    http_status = HTTPStatus.BAD_GATEWAY
    error_code = "ai_provider_error"

    def __init__(self, provider: str = "openai", message: str = "LLM request failed") -> None:
        super().__init__(f"[{provider}] {message}")
        self.provider = provider


class EmbeddingError(AIProviderError):
    """Embedding generation failed."""
    error_code = "embedding_error"

    def __init__(self, message: str = "Embedding generation failed") -> None:
        super().__init__("openai", message)


# ── Data Sources ──────────────────────────────────────────────────────────────

class VectorStoreError(VectraIQError):
    """Qdrant operation failed."""
    http_status = HTTPStatus.SERVICE_UNAVAILABLE
    error_code = "vector_store_error"


class DatabaseError(VectraIQError):
    """PostgreSQL operation failed."""
    http_status = HTTPStatus.SERVICE_UNAVAILABLE
    error_code = "database_error"


class SQLGenerationError(VectraIQError):
    """SQL generation or validation failed."""
    http_status = HTTPStatus.UNPROCESSABLE_ENTITY
    error_code = "sql_generation_error"


class SQLExecutionError(DatabaseError):
    """Generated SQL failed to execute."""
    error_code = "sql_execution_error"


# ── External Services ─────────────────────────────────────────────────────────

class CacheError(VectraIQError):
    """Cache operation failed (non-fatal; caller should handle gracefully)."""
    http_status = HTTPStatus.SERVICE_UNAVAILABLE
    error_code = "cache_error"


class WebSearchError(VectraIQError):
    """Web search (Tavily) request failed."""
    http_status = HTTPStatus.BAD_GATEWAY
    error_code = "web_search_error"


# ── Resource ──────────────────────────────────────────────────────────────────

class NotFoundError(VectraIQError):
    """Requested resource not found."""
    http_status = HTTPStatus.NOT_FOUND
    error_code = "not_found"


class ConflictError(VectraIQError):
    """Resource already exists."""
    http_status = HTTPStatus.CONFLICT
    error_code = "conflict"
