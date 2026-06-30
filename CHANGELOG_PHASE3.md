# CHANGELOG_PHASE3.md — VectraIQ Phase 3

## [2.1.0] — 2026-06-30

### New Files

- **`vectraiq/exceptions.py`** — 15-class domain exception hierarchy. All application
  errors derive from `VectraIQError` carrying `http_status`, `error_code`, and `message`.

- **`vectraiq/logging_config.py`** — Structured loguru setup. Supports JSON mode
  (production) and human-readable mode (development). Bridges stdlib `logging` so
  uvicorn, fastapi, and third-party libraries route through loguru. Provides
  `request_id_var` contextvars and `get_request_id()` / `set_request_id()` helpers.

- **`vectraiq/observability.py`** — Timing and metrics hooks. `timed_ai_call()` context
  manager wraps every LLM call and emits `AICallMetrics`. `timed_search()` wraps
  vector search calls. `record_ai_call()` and `record_search()` are pluggable sinks —
  replace their bodies to push to Langfuse or OTEL without touching call sites.

- **`vectraiq/middleware/request_context.py`** — ASGI middleware that generates or
  propagates `X-Request-ID`, measures end-to-end latency, and emits a structured
  access log line on every response.

### Enhanced: Application Factory (`vectraiq/main.py`)

- Added `lifespan()` context manager for startup/shutdown events
- Startup now calls `configure_logging()` and warns on missing critical config
- Added `CORSMiddleware` (CORS headers, `expose_headers: [X-Request-ID]`)
- Added `RequestContextMiddleware` (request ID, timing, access log)
- Registered 4 global exception handlers:
  - `VectraIQError` → domain-typed error response
  - `HTTPException` → wrapped in error envelope
  - `RequestValidationError` → 422 with field-level `field_errors` list
  - `Exception` → opaque 500 (full traceback logged server-side)
- Added OpenAPI tag descriptions, app description, full endpoint docs
- Changed to `create_app()` factory pattern (testable, explicit)

### Enhanced: Configuration (`vectraiq/config.py`)

- Added `field_validator` for `log_level`, `storage_backend`, `reranker_backend`
- Added `@property redis_enabled` and `tavily_enabled` convenience checks
- Added `extra = "ignore"` — arbitrary env vars no longer crash startup
- Inline section comments for every settings group

### Enhanced: Models (`vectraiq/models.py`)

- Added `APIError` + `ErrorResponse` — standardized error envelope used by all handlers
- Added `AuthRequest` — typed body for auth endpoints (replaces `AuthBody`)
- Added `TokenResponse` — typed auth success response with `expires_in`
- Added `CacheTierStats` + `CacheStatsResponse` — typed admin cache stats
- Added `ServiceHealth` — typed health check response
- Added `SqlApprovalRequest` — moved from inline `BaseModel` in `api/query.py`
- Added `request_id: str` field to `ChatResponse`
- All `Field()` calls now include `description=` for OpenAPI schema docs
- Removed `ChatRequest` (was defined but never used in a route)

### Enhanced: Auth Middleware (`vectraiq/middleware/auth.py`)

- Raises `TokenExpiredError`, `AuthenticationError`, `AuthorizationError` (domain exceptions)
- Removed `HTTPException` imports (auth errors now route through global handler)
- Renamed `security` → `_bearer` (private, module-internal)

### Enhanced: Rate Limiter (`vectraiq/middleware/rate_limiter.py`)

- Added module-level `_user_limiter` singleton (avoids per-call `RateLimiter()` instantiation)
- `is_allowed_user()` uses singleton when limit/window match global settings
- Full module docstring added

### Enhanced: Auth API (`vectraiq/api/auth.py`)

- Uses `AuthRequest` and `TokenResponse` (clean, typed I/O)
- Raises domain exceptions (`RateLimitError`, `ConflictError`, `AuthenticationError`)
- Login returns generic error message to prevent user enumeration
- Added OpenAPI `responses=` metadata per endpoint
- Added endpoint `summary` strings

### Enhanced: Query API (`vectraiq/api/query.py`)

- Extracted `_apply_security_pipeline()` — 9-step pipeline in one named function
- Raises typed domain exceptions (no bare `HTTPException`)
- Uses `timer()` from observability for latency tracking
- Structured `logger.info()` on query completion (intent, cache, latency)
- Proper `ResponseMetadata` reconstruction from LangGraph dict result
- Echoes `request_id` in `ChatResponse`
- `SqlExecuteRequest` replaced by imported `SqlApprovalRequest` from models

### Enhanced: Admin API (`vectraiq/api/admin.py`)

- Uses `ServiceHealth`, `CacheStatsResponse`, `CacheTierStats` (typed responses)
- `_ping_redis()` short-circuits when `settings.redis_enabled` is False
- `_ping_openai()` short-circuits when API key is missing
- `_ping_tavily()` returns `True` when not configured (avoids false "down" alerts)
- `cache_clear` logs the admin username

### Enhanced: LLM Service (`vectraiq/ai/llm_service.py`)

- Wraps `generate()` and `generate_with_json()` with `timed_ai_call()` context manager
- Feeds `prompt_tokens`, `completion_tokens`, `total_tokens` into observability record
- Docstrings on both functions

### Enhanced: Reranker (`vectraiq/ai/reranking.py`)

- Added module-level `_reranker = Reranker()` singleton
- Added `rerank_chunks()` convenience function delegating to singleton
- CrossEncoder model now loads once per process (was once per request)
- Log message when CrossEncoder model loads

### Enhanced: RAG Service (`vectraiq/ai/rag_service.py`)

- Added module-level `_sql_service = SQLService()` — schema cache now actually hits
- Added module-level `_hyde_retriever = HyDERetriever()`
- Uses `rerank_chunks()` instead of `Reranker().rerank()`
- Improved `logger.info()` precision on CRAG score (`{:.2f}`)
- Both inline paths use `_sql_service` singleton

---

### Performance

| Issue | Fix | Expected Impact |
|---|---|---|
| CrossEncoder loads on every reranked request | Module-level `_reranker` singleton | ~2–5s saved per reranked request |
| SQLService schema introspection per rag_service call | Module-level `_sql_service` singleton | DB round-trip eliminated on second SQL query |
| `RateLimiter()` instantiated per rate-check | Module-level `_user_limiter` singleton | Minor; avoids repeated object creation |
| `HyDERetriever()` instantiated per retrieve | Module-level `_hyde_retriever` singleton | Minor init cost eliminated |

---

### Breaking Changes for Clients

None. All API endpoints, request shapes, and response shapes are backward-compatible.

Internal callers importing `AuthBody` from `vectraiq.api.auth` should switch to `AuthRequest` from `vectraiq.models` — `AuthBody` no longer exists.

### No-Change Guarantee

The following AI pipeline components are **structurally identical** to Phase 2:
- LangGraph state machine (`vectraiq/core/graph.py`) — untouched
- CRAG pipeline (`vectraiq/ai/crag.py`) — untouched
- HyDE retriever (`vectraiq/ai/hyde.py`) — untouched
- Self-RAG reflection (`vectraiq/ai/self_reflective.py`) — untouched
- Vector store (`vectraiq/ai/vector_store.py`) — untouched
- Sparse index (`vectraiq/ai/sparse_vector_service.py`) — untouched
- Embedding service (`vectraiq/ai/embedding_service.py`) — untouched
- Web search (`vectraiq/ai/web_search.py`) — untouched
- Content moderation (`vectraiq/security/content_moderation.py`) — untouched
- Spotlighting (`vectraiq/security/spotlighting.py`) — untouched
- System prompt (`vectraiq/security/system_prompt.py`) — untouched
- Input guard (`vectraiq/security/input_guard.py`) — untouched
- Input restructuring (`vectraiq/security/input_restructuring.py`) — untouched
- Token budget (`vectraiq/security/token_budget.py`) — untouched
- Storage layer (`vectraiq/storage/`) — untouched
- Cache service (`vectraiq/cache/`) — untouched
