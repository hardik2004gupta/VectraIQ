# MIGRATION_LOG.md — VectraIQ Phase 2

Chronological record of every file created, modified, or fixed during Phase 2.

---

## Files Created — vectraiq package

| File | Source | Notes |
|---|---|---|
| `vectraiq/__init__.py` | new | `__version__ = "2.0.0"` |
| `vectraiq/config.py` | `app/config.py` | Removed vanna_* fields; added sql_llm_model, sql_temperature |
| `vectraiq/models.py` | `app/models.py` | Extracted shared `_check_injection()` — eliminated duplicate validators |
| `vectraiq/main.py` | `app/main.py` | Updated imports; title → "VectraIQ" |
| `vectraiq/storage/__init__.py` | new | |
| `vectraiq/storage/backend.py` | `app/storage/storage_backend.py` | Renamed file; updated imports |
| `vectraiq/storage/local.py` | `app/storage/local_storage.py` | **Implemented from scratch** — was empty (1-line file) |
| `vectraiq/storage/s3.py` | `app/storage/s3_storage.py` | Renamed file; updated imports |
| `vectraiq/cache/query_cache.py` | `app/services/query_cache_service.py` | Moved to cache/; module-level singleton; documented Redis clear limitation |
| `vectraiq/cache/doc_cache.py` | `app/services/doc_cache_service.py` | Moved to cache/; updated imports |
| `vectraiq/ai/llm_service.py` | `app/services/llm_service.py` | Module-level `_client` singleton |
| `vectraiq/ai/embedding_service.py` | `app/services/embedding_service.py` | Updated imports |
| `vectraiq/ai/sparse_vector_service.py` | `app/services/sparse_vector_service.py` | Updated imports |
| `vectraiq/ai/vector_store.py` | `app/services/vector_store.py` | Updated imports |
| `vectraiq/ai/reranking.py` | `app/services/reranking.py` | Updated imports |
| `vectraiq/ai/web_search.py` | `app/services/web_search.py` | Updated imports |
| `vectraiq/ai/crag.py` | `app/services/crag.py` | Updated imports |
| `vectraiq/ai/hyde.py` | `app/services/hyde.py` | Updated imports |
| `vectraiq/ai/self_reflective.py` | `app/services/self_reflective.py` | Updated imports |
| `vectraiq/ai/router_service.py` | `app/services/router_service.py` | **Removed `_DOCUMENT_HINTS`** (stale ML paper terms) |
| `vectraiq/ai/sql_service.py` | `app/services/sql_service.py` | **Improved `is_select_only()`**; vanna_ prefix → sql_ |
| `vectraiq/ai/document_processor.py` | `app/services/document_processor.py` | Updated imports |
| `vectraiq/ai/rag_service.py` | `app/services/rag_service.py` | **Removed `run_rag_with_trace_no_cache` alias** |
| `vectraiq/security/__init__.py` | new | |
| `vectraiq/security/input_restructuring.py` | `app/security/input_restructuring.py` | **Renamed `summarize_text()` → `truncate_to_token_limit()`** |
| `vectraiq/security/input_guard.py` | `app/security/input_guard.py` | Updated imports |
| `vectraiq/security/content_moderation.py` | `app/security/content_moderation.py` | **Removed IPv4 redaction pattern** (breaks K8s networking answers) |
| `vectraiq/security/output_validator.py` | `app/security/output_validator.py` | Updated imports |
| `vectraiq/security/spotlighting.py` | `app/security/spotlighting.py` | Updated imports |
| `vectraiq/security/system_prompt.py` | `app/security/system_prompt.py` | Removed JSON response mandate (was never enforced) |
| `vectraiq/security/token_budget.py` | `app/security/token_budget.py` | **Added graceful Redis degradation** (allow + warn instead of 500) |
| `vectraiq/middleware/__init__.py` | new | |
| `vectraiq/middleware/auth.py` | `app/middleware/auth.py` | Updated imports |
| `vectraiq/middleware/rate_limiter.py` | `app/middleware/rate_limiter.py` | **Added graceful Redis degradation** (allow + warn instead of 500) |
| `vectraiq/core/__init__.py` | new | |
| `vectraiq/core/state.py` | `app/core/state.py` | Updated imports |
| `vectraiq/core/graph.py` | `app/core/graph.py` | Updated all imports to `vectraiq.*` |
| `vectraiq/api/__init__.py` | new | |
| `vectraiq/api/auth.py` | `app/api/auth.py` | **Added `AuthBody(BaseModel)`** (was untyped `dict`) |
| `vectraiq/api/query.py` | `app/api/query.py` | Updated all imports to `vectraiq.*` |
| `vectraiq/api/admin.py` | `app/api/admin.py` | Updated all imports to `vectraiq.*` |

---

## Files Modified — external

| File | Change |
|---|---|
| `scripts/serve.py` | `app.main:app` → `vectraiq.main:app` |
| `scripts/seed_db.py` | `from app.middleware.auth` → `from vectraiq.middleware.auth`; `app.models/services` → `vectraiq.models/ai` |
| `eval/invokers.py` | All `from app.*` → `from vectraiq.*`; `run_rag_with_trace_no_cache` → `run_rag_with_trace` |
| `eval/ragas_adapter.py` | `from app.config` → `from vectraiq.config` |
| `Makefile` | `uvicorn app.main:app` → `uvicorn vectraiq.main:app` |
| `pyproject.toml` | name `adv-rag`→`vectraiq`; version `0.1.0`→`2.0.0`; `packages = ["app"]`→`["vectraiq"]`; removed `vanna[openai,postgres]` |

---

## Files NOT Modified (preserved)

- `app/` — entire original package, all files untouched
- `eval/` (except invokers.py and ragas_adapter.py)
- `seed/` — all migrations and corpus files
- `docker-compose.yml`, `Dockerfile`
- `.env.example`
- `AUDIT_REPORT.md`, `CLAUDE.md`
- All Phase 1 architecture docs
