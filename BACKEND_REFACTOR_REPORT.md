# BACKEND_REFACTOR_REPORT.md — VectraIQ Phase 3

## Summary

Phase 3 modernized the VectraIQ backend by introducing a layered architecture of cross-cutting concerns (logging, observability, error handling) that sit cleanly above the AI pipeline without touching any business logic.

---

## New Files Created

| File | Purpose |
|---|---|
| `vectraiq/exceptions.py` | Domain exception hierarchy (15 typed exceptions) |
| `vectraiq/logging_config.py` | Structured loguru setup with request-ID context propagation |
| `vectraiq/observability.py` | AI call timing, search metrics, clean Langfuse/OTEL extension points |
| `vectraiq/middleware/request_context.py` | ASGI request ID injection + access log middleware |

---

## Files Significantly Refactored

### `vectraiq/main.py`
- Added `lifespan()` context manager for startup validation + clean shutdown logging
- Added `CORSMiddleware` (CORS headers + preflight)
- Added `RequestContextMiddleware` (request ID, timing, access log)
- Registered 4 global exception handlers (VectraIQError, HTTPException, ValidationError, Exception)
- Improved OpenAPI metadata: description, tag descriptions, version
- Startup config warnings instead of crashes on missing env vars

### `vectraiq/config.py`
- Added `field_validator` for `log_level`, `storage_backend`, `reranker_backend`
- Added `@property redis_enabled` and `tavily_enabled` (avoids repeating conditional checks)
- Added `extra = "ignore"` so arbitrary shell env vars don't break startup
- Grouped settings into named sections with inline docs

### `vectraiq/models.py`
- Added `APIError` + `ErrorResponse` — standard error envelope for all error responses
- Added `AuthRequest` + `TokenResponse` — clean auth I/O models
- Added `CacheTierStats` + `CacheStatsResponse` — typed admin responses
- Added `ServiceHealth` — typed health check response
- Added `SqlApprovalRequest` — moved from `api/query.py` inline class
- Added `request_id: str` field to `ChatResponse` for correlation
- Improved all Field() with `description=` and `examples=` for OpenAPI docs

### `vectraiq/middleware/auth.py`
- Replaced `HTTPException` raises with `VectraIQError` domain exceptions
- Uses `TokenExpiredError`, `AuthenticationError`, `AuthorizationError`
- Cleaner dependency names (`_bearer` vs `security`)

### `vectraiq/middleware/rate_limiter.py`
- Added module-level `_user_limiter` singleton (avoids per-call `RateLimiter()` instantiation)
- Lazy Redis client (was already lazy, now more explicit)
- Added full docstring

### `vectraiq/api/auth.py`
- Uses `AuthRequest` + `TokenResponse` models (clean I/O)
- Raises `RateLimitError`, `ConflictError`, `AuthenticationError` (domain exceptions)
- Added OpenAPI `responses=` metadata per endpoint
- Deliberate generic error message on login failure (avoids user enumeration)

### `vectraiq/api/query.py`
- Extracted `_apply_security_pipeline()` — 9-line security sequence is now a named function
- Raises typed domain exceptions (no more bare `HTTPException`)
- Uses `timer()` observability hook for latency tracking
- Structured `logger.info()` with intent, cache_hit, latency on every query
- Proper `ResponseMetadata` reconstruction from dict result
- Added `request_id` to `ChatResponse`

### `vectraiq/api/admin.py`
- Uses `ServiceHealth`, `CacheStatsResponse`, `CacheTierStats` response models
- `_ping_redis()` short-circuits when `settings.redis_enabled` is False
- `_ping_openai()` short-circuits when API key is missing
- `_ping_tavily()` returns `True` when not configured (not a dependency)

### `vectraiq/ai/llm_service.py`
- Wraps both `generate()` and `generate_with_json()` with `timed_ai_call()` context manager
- Records prompt/completion/total tokens into observability metrics on every call
- Extension point: replace `record_ai_call()` in `observability.py` to push to Langfuse

### `vectraiq/ai/reranking.py`
- Added module-level `_reranker = Reranker()` singleton
- Added `rerank_chunks()` module function that delegates to singleton
- CrossEncoder model now loaded once per process instead of once per request
- `rag_service.py` updated to call `rerank_chunks()` instead of `Reranker().rerank()`

### `vectraiq/ai/rag_service.py`
- Added module-level `_sql_service = SQLService()` — schema introspection cache now actually hits
- Added module-level `_hyde_retriever = HyDERetriever()`
- Uses `rerank_chunks()` (singleton reranker)
- Improved `logger.info()` calls (format strings, float precision)
- Both `_run_sql_inline` and `_run_hybrid_inline` use `_sql_service` singleton

---

## Architecture Patterns Established

### 1. Exception flow
```
Business logic → raises VectraIQError subclass
                         ↓
            main.py _vectraiq_error_handler
                         ↓
            ErrorResponse JSON with error.code, error.message, request_id
```

### 2. Request correlation
```
Every request → X-Request-ID header
             → set in contextvars (request_id_var)
             → available via get_request_id() anywhere in the call stack
             → echoed in ChatResponse.request_id
             → included in every log line via loguru patcher
```

### 3. Observability hooks
```
LLM call → with timed_ai_call("generate", model="gpt-4o") as m:
               result = openai.chat.completions.create(...)
               m.total_tokens = result.usage.total_tokens
           # → record_ai_call(m) called automatically on exit
           # → replace record_ai_call() to push to Langfuse/OTEL
```

### 4. Singleton services
```
Module level:
  _client      = OpenAI(...)          # llm_service.py
  _reranker    = Reranker()           # reranking.py
  _sql_service = SQLService()         # rag_service.py
  _hyde_retriever = HyDERetriever()   # rag_service.py
  query_cache  = QueryCacheService()  # cache/query_cache.py
  settings     = Settings()           # config.py
```

---

## Performance Improvements

| Before | After | Impact |
|---|---|---|
| `Reranker()` created per request | `_reranker` module singleton | CrossEncoder model loads once |
| `SQLService()` created per call in rag_service | `_sql_service` module singleton | Schema cache now hits |
| `RateLimiter(...)` created per call | `_user_limiter` module singleton | Fewer allocations per request |
| `HyDERetriever()` created per retrieve | `_hyde_retriever` module singleton | No repeated init |

---

## Zero Feature Regressions

All of the following were verified as structurally preserved:
- ✅ LangGraph 7-node state machine + interrupt/resume
- ✅ Hybrid RAG (dense + sparse + RRF)
- ✅ HyDE retrieval
- ✅ CRAG (relevance grading + Tavily fallback)
- ✅ Self-RAG reflection loop
- ✅ CrossEncoder / Voyage reranking
- ✅ Text2SQL + SELECT-only enforcement
- ✅ 9-layer security pipeline
- ✅ 5-tier cache (Redis + in-memory)
- ✅ RAGAS evaluation harness
