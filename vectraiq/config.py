"""
VectraIQ application settings.

Loaded once at import time from environment variables / .env file.
Grouped by subsystem for readability. All secrets are strings with
empty defaults so the app can start (with warnings) without a full .env.
"""

from __future__ import annotations

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # Don't error on extra env vars from the shell
        extra="ignore",
    )

    # ── LLM ──────────────────────────────────────────────────────────────────
    openai_api_key: str = ""
    llm_model_answer: str = "gpt-4o"
    llm_model_grader: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"

    # ── Vector store (Qdrant) ─────────────────────────────────────────────────
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "documents"

    # ── Database (PostgreSQL) ─────────────────────────────────────────────────
    database_url: str = "postgresql://postgres:postgres@localhost:5432/adv_rag"

    # ── Cache (Upstash Redis) ─────────────────────────────────────────────────
    upstash_redis_url: str = ""
    upstash_redis_token: str = ""
    # TTLs in seconds
    cache_ttl_embeddings: int = 604_800   # 7 days
    cache_ttl_rag: int = 3_600            # 1 hour
    cache_ttl_sql_gen: int = 86_400       # 24 hours
    cache_ttl_sql_result: int = 900       # 15 minutes
    cache_ttl_intent: int = 86_400        # 24 hours

    # ── Storage ───────────────────────────────────────────────────────────────
    storage_backend: str = "local"        # "local" | "s3"
    s3_cache_bucket: str = "vectraiq-cache"
    aws_region: str = "us-east-1"

    # ── Web search ────────────────────────────────────────────────────────────
    tavily_api_key: str = ""

    # ── Authentication ────────────────────────────────────────────────────────
    jwt_secret: str = ""
    jwt_expiration_minutes: int = 60
    auth_login_rate_limit_per_min: int = 5
    auth_register_rate_limit_per_hour: int = 3

    # ── Rate limiting ─────────────────────────────────────────────────────────
    rate_limit_requests: int = 20
    rate_limit_window_seconds: int = 60
    max_tokens_per_user_daily: int = 100_000

    # ── Input handling ────────────────────────────────────────────────────────
    max_input_tokens: int = 3_000
    reserved_context_tokens: int = 1_000
    reserved_output_tokens: int = 1_000

    # ── Security thresholds ───────────────────────────────────────────────────
    prompt_injection_threshold: float = 0.75
    toxicity_threshold: float = 0.75
    output_toxicity_threshold: float = 0.5
    max_validation_retries: int = 2

    # ── RAG pipeline feature flags ─────────────────────────────────────────────
    hyde_num_hypotheses: int = 3
    hyde_enabled_by_default: bool = False
    hybrid_search_enabled: bool = True
    rrf_k: int = 60
    reranker_backend: str = "local"       # "local" | "voyage"
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    voyage_api_key: str = ""
    voyage_model: str = "rerank-2.5"
    reranker_initial_top_k: int = 20
    reranking_enabled_by_default: bool = True
    crag_relevance_threshold: float = 0.7
    crag_ambiguous_threshold: float = 0.5
    crag_enabled_by_default: bool = True
    reflection_min_score: float = 0.85
    max_reflection_retries: int = 2
    self_reflective_enabled_by_default: bool = False

    # ── SQL generation ────────────────────────────────────────────────────────
    sql_llm_model: str = "gpt-4o"
    sql_temperature: float = 0.0

    # ── CORS ──────────────────────────────────────────────────────────────────
    # Comma-separated list of allowed frontend origins.
    # Example: http://localhost:3000,https://app.vectraiq.io
    frontend_origins: list[str] = ["http://localhost:3000"]

    # ── Observability ─────────────────────────────────────────────────────────
    log_json: bool = False                # Set true in production
    log_level: str = "INFO"

    # Langfuse tracing (optional — disabled when keys are absent)
    langfuse_secret_key: str = ""
    langfuse_public_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"
    langfuse_enabled: bool = True

    # OpenTelemetry (optional — disabled when endpoint is absent)
    otel_exporter_otlp_endpoint: str = ""
    otel_enabled: bool = True

    # ── Validators ────────────────────────────────────────────────────────────

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in valid:
            raise ValueError(f"log_level must be one of {valid}; got {v!r}")
        return upper

    @field_validator("storage_backend")
    @classmethod
    def validate_storage_backend(cls, v: str) -> str:
        valid = {"local", "s3"}
        if v not in valid:
            raise ValueError(f"storage_backend must be one of {valid}; got {v!r}")
        return v

    @field_validator("reranker_backend")
    @classmethod
    def validate_reranker_backend(cls, v: str) -> str:
        valid = {"local", "voyage"}
        if v not in valid:
            raise ValueError(f"reranker_backend must be one of {valid}; got {v!r}")
        return v

    @property
    def redis_enabled(self) -> bool:
        """True when Upstash credentials are configured."""
        return bool(self.upstash_redis_url and self.upstash_redis_token)

    @property
    def tavily_enabled(self) -> bool:
        """True when Tavily API key is configured."""
        return bool(self.tavily_api_key)


settings = Settings()
