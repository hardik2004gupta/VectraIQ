"""
VectraIQ Pydantic models — request, response, and error schemas.

All API responses share the same error envelope so clients can detect
failures with a single field check (`error` present → failure).
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


# ── Shared injection-pattern validator ───────────────────────────────────────

_INJECTION_PATTERNS = [
    r"(?i)(ignore\s+previous|ignore\s+above|forget\s+your\s+instructions)",
    r"(?i)(system\s*prompt|reveal\s+your\s+instructions|show\s+your\s+prompt)",
    r"(?i)(you\s+are\s+now|new\s+instructions|override\s+previous)",
    r"(?i)(<\s*script|javascript:|on\w+\s*=)",
]


def _check_injection(value: str, field_label: str) -> str:
    """Raise ValueError if value matches any prompt-injection pattern."""
    value = value.strip()
    if not value:
        raise ValueError(f"{field_label} cannot be empty or whitespace only")
    for pattern in _INJECTION_PATTERNS:
        if re.search(pattern, value):
            raise ValueError(f"{field_label} contains potentially malicious content")
    if re.match(r"^[\W_]+$", value):
        raise ValueError(f"{field_label} must contain actual text content")
    return value


# ── Error envelope ────────────────────────────────────────────────────────────

class APIError(BaseModel):
    """Standardized error response returned by all error handlers.

    Shape::

        {
            "error": {
                "code": "rate_limit_exceeded",
                "message": "Rate limit exceeded. Please retry later.",
                "details": {}
            },
            "request_id": "550e8400-..."
        }
    """

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: APIError
    request_id: str = ""


# ── Request models ─────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    """POST /query — main RAG query."""

    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Natural language question to answer.",
        examples=["How do I restart a crashed Kubernetes pod?"],
    )
    enable_rerank: bool = Field(
        default=False,
        description="Enable CrossEncoder / Voyage reranking of retrieved chunks.",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Number of chunks to return from the vector store.",
    )
    enable_hyde: bool = Field(
        default=False,
        description="Enable HyDE (Hypothetical Document Embeddings) retrieval.",
    )
    search_mode: Literal["dense", "sparse", "hybrid"] = Field(
        default="dense",
        description="Vector search strategy.",
    )
    enable_crag: bool = Field(
        default=True,
        description="Enable CRAG relevance grading with Tavily web fallback.",
    )
    enable_self_reflective: bool = Field(
        default=False,
        description="Enable Self-RAG answer quality reflection loop.",
    )

    @field_validator("question")
    @classmethod
    def validate_question(cls, v: str) -> str:
        return _check_injection(v, "Question")


class SqlApprovalRequest(BaseModel):
    """POST /query/sql/execute — approve or reject a pending SQL statement."""

    query_id: str = Field(..., description="Thread ID from the pending SQL response.")
    approved: bool = Field(..., description="True to execute the SQL; False to cancel.")


# ── Sub-models used in responses ──────────────────────────────────────────────

class RetrievedChunk(BaseModel):
    """A document chunk retrieved from the vector store."""
    text: str
    source: str
    score: float = 0.0


class RetrievedChunkPreview(BaseModel):
    """Abbreviated chunk included in API responses (same shape, clearer intent)."""
    text: str
    source: str
    score: float = 0.0


class CRAGEvaluation(BaseModel):
    """CRAG relevance grading result."""
    relevance_score: float = 0.0
    relevance_label: str = ""
    confidence: float = 0.0
    reasoning: str = ""


class ReflectionResult(BaseModel):
    """Self-RAG reflection result on a generated answer."""
    reflection_score: float = 0.0
    needs_regeneration: bool = False
    refined_question: str = ""
    reasoning: str = ""


class ResponseMetadata(BaseModel):
    """Non-critical metadata attached to every ChatResponse."""
    route: str = Field(default="rag", description="Intent route: rag | sql | hybrid")
    retrieved_chunks: list[RetrievedChunkPreview] = Field(default_factory=list)
    cache_hit: bool = False
    reflection_iterations: int = Field(default=0, ge=0)
    reflection_score: float | None = None
    refined_question: str | None = None


class PendingSQLBlock(BaseModel):
    """Represents a generated SQL query awaiting user approval."""
    sql: str = Field(..., description="The generated SQL SELECT statement.")
    query_id: str = Field(..., description="Thread ID to resume with /query/sql/execute.")
    explanation: str = Field(default="", description="LLM explanation of what the query does.")


# ── Primary response models ───────────────────────────────────────────────────

class ChatResponse(BaseModel):
    """Response from POST /query and POST /query/sql/execute."""

    answer: str = Field(default="", description="Generated answer text.")
    sources: list[str] = Field(
        default_factory=list,
        description="Deduplicated list of source document names.",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Answer confidence score in [0, 1].",
    )
    pending_sql: PendingSQLBlock | None = Field(
        default=None,
        description="Populated when a SQL query requires user approval before execution.",
    )
    cache_hit: bool = Field(
        default=False,
        description="True when the answer was served from cache.",
    )
    request_id: str = Field(
        default="",
        description="Echo of the X-Request-ID header for correlation.",
    )
    metadata: ResponseMetadata = Field(default_factory=ResponseMetadata)


# ── Auth models ───────────────────────────────────────────────────────────────

class AuthRequest(BaseModel):
    """Request body for /auth/register and /auth/login."""

    username: str = Field(..., min_length=3, max_length=64, description="Username.")
    password: str = Field(..., min_length=8, max_length=128, description="Password.")


class TokenResponse(BaseModel):
    """Returned on successful auth."""
    token: str = Field(..., description="JWT bearer token.")
    token_type: str = Field(default="bearer")
    expires_in: int = Field(..., description="Token TTL in seconds.")


# ── Admin models ──────────────────────────────────────────────────────────────

class CacheTierStats(BaseModel):
    hits: int = 0
    misses: int = 0
    sets: int = 0
    hit_rate: float = 0.0


class CacheStatsResponse(BaseModel):
    embedding: CacheTierStats = Field(default_factory=CacheTierStats)
    rag: CacheTierStats = Field(default_factory=CacheTierStats)
    sql_gen: CacheTierStats = Field(default_factory=CacheTierStats)
    sql_result: CacheTierStats = Field(default_factory=CacheTierStats)
    intent_router: CacheTierStats = Field(default_factory=CacheTierStats)


class ServiceHealth(BaseModel):
    status: str = Field(..., description="'ok' or 'degraded'")
    qdrant: bool
    postgres: bool
    redis: bool
    openai: bool
    tavily: bool
