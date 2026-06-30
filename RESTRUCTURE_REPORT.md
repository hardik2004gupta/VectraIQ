# RESTRUCTURE_REPORT.md — VectraIQ Phase 2

## Summary

Phase 2 restructured the `enterprise-level-rag` repository by creating the `vectraiq` Python package as the authoritative replacement for `app/`. All AI services, security pipeline, caching, middleware, API, and core LangGraph components were migrated with updated import paths, dead code removed, and several bugs fixed in the process. The `app/` package is preserved untouched as a safety net.

---

## Scope

| Dimension | Before | After |
|---|---|---|
| Package name | `app` | `vectraiq` |
| Project name (pyproject.toml) | `adv-rag` | `vectraiq` |
| Version | `0.1.0` | `2.0.0` |
| AI services location | `app/services/` | `vectraiq/ai/` |
| Cache services location | `app/services/` (mixed) | `vectraiq/cache/` |
| Storage file names | `storage_backend.py`, `local_storage.py`, `s3_storage.py` | `backend.py`, `local.py`, `s3.py` |
| Dead dependencies | `vanna[openai,postgres]` | removed |
| Dead config fields | `vanna_model`, `vanna_temperature`, `vanna_seed` | removed |
| Dead aliases | `run_rag_with_trace_no_cache` | removed |
| Dead hints | `_DOCUMENT_HINTS` (ML paper terms) | removed |

---

## New Package Structure

```
vectraiq/
  __init__.py          # __version__ = "2.0.0"
  config.py            # Pydantic Settings (cleaned)
  models.py            # Pydantic request/response models (deduplicated validators)
  main.py              # FastAPI app factory
  api/
    __init__.py
    auth.py            # /auth/register, /auth/login (+ AuthBody model)
    query.py           # /query, /query/sql/execute
    admin.py           # /admin/health, /admin/cache/stats, /admin/cache/clear
  ai/
    llm_service.py     # OpenAI generate/generate_with_json (module-level client)
    embedding_service.py
    sparse_vector_service.py
    vector_store.py
    reranking.py
    web_search.py
    crag.py
    hyde.py
    self_reflective.py
    router_service.py  # intent classification (stale _DOCUMENT_HINTS removed)
    sql_service.py     # Text2SQL (improved is_select_only, vanna_ prefix removed)
    document_processor.py
    rag_service.py     # Full RAG pipeline (no_cache alias removed)
  cache/
    query_cache.py     # 5-tier cache (module-level singleton)
    doc_cache.py
  security/
    __init__.py
    input_restructuring.py   # truncate_to_token_limit() (renamed from summarize_text)
    input_guard.py
    content_moderation.py    # IP redaction removed (breaks K8s answers)
    output_validator.py
    spotlighting.py
    system_prompt.py
    token_budget.py          # graceful Redis degradation added
  middleware/
    __init__.py
    auth.py            # JWT HS256
    rate_limiter.py    # graceful Redis degradation added
  core/
    __init__.py
    state.py           # GraphState TypedDict
    graph.py           # LangGraph 7-node graph
  storage/
    __init__.py
    backend.py         # Abstract StorageBackend + factory
    local.py           # LocalStorage IMPLEMENTED (was empty in app/)
    s3.py              # S3Storage
```

---

## Bugs Fixed

| # | Bug | Fix location |
|---|---|---|
| 1 | `local_storage.py` was empty (1 line) | `vectraiq/storage/local.py` — full implementation with path traversal protection |
| 2 | IP addresses redacted in PII scan (breaks K8s networking answers) | `vectraiq/security/content_moderation.py` — IPv4 pattern removed |
| 3 | `summarize_text()` misleadingly named (greedy sentence selection, not LLM) | `vectraiq/security/input_restructuring.py` — renamed to `truncate_to_token_limit()` |
| 4 | Auth body was untyped `dict` | `vectraiq/api/auth.py` — `AuthBody(BaseModel)` added |
| 5 | Rate limiter raised 500 when Redis unavailable | `vectraiq/middleware/rate_limiter.py` — graceful degradation (allow + warn) |
| 6 | Token budget raised 500 when Redis unavailable | `vectraiq/security/token_budget.py` — graceful degradation (allow + warn) |
| 7 | Duplicate injection validators in models.py | `vectraiq/models.py` — shared `_check_injection()` function |
| 8 | `is_select_only()` did not strip SQL comments or detect multi-statement | `vectraiq/ai/sql_service.py` — comment stripping + semicolon check |

---

## Dead Code Removed

| Item | Location | Reason |
|---|---|---|
| `_DOCUMENT_HINTS` | `router_service.py` | ML paper terms (gsm8k, humaneval, qkv, llada) unrelated to K8s |
| `run_rag_with_trace_no_cache` | `rag_service.py` | Was `= run_rag_with_trace` (identity alias with misleading name) |
| `vanna_model`, `vanna_temperature`, `vanna_seed` | `config.py` | Vanna dependency removed; replaced by `sql_llm_model`, `sql_temperature` |
| `vanna[openai,postgres]` | `pyproject.toml` | Dead dependency |

---

## Files Updated (external)

| File | Change |
|---|---|
| `scripts/serve.py` | `app.main:app` → `vectraiq.main:app` |
| `scripts/seed_db.py` | All `from app.*` → `from vectraiq.*` |
| `eval/invokers.py` | Imports updated; `run_rag_with_trace_no_cache` → `run_rag_with_trace` |
| `eval/ragas_adapter.py` | `from app.config` → `from vectraiq.config` |
| `Makefile` | `app.main:app` → `vectraiq.main:app` |
| `pyproject.toml` | Name, version, packages, removed vanna |

---

## What Was NOT Changed

- `app/` package — preserved intact as safety net (no deletions)
- All LangGraph nodes and graph topology
- All AI pipeline logic (RAG, HyDE, CRAG, Self-RAG, Text2SQL, Reranker)
- All security layers and order of execution
- All API endpoints and response shapes
- All evaluation harness files (beyond import updates)
- Database schema, migrations, seed data
- Docker/infra configuration

---

## Remaining Known Issues (from AUDIT_REPORT.md)

| # | Issue | Status |
|---|---|---|
| 3 | `_build_sparse_index()` runs on every query (no caching) | Not fixed — architectural change required |
| 4 | `Reranker()` instantiated per request | Not fixed — singleton refactor out of scope |
| 5 | `/documents/upload` endpoint missing | Not fixed — new feature |
| 6 | Redis `cache.clear()` is no-op for remote cache | Documented in code comment; SDK limitation |
| 7 | SQL approval not user-scoped | Not fixed — security improvement required |
| 8 | Dual execution paths (rag_service + graph) | Preserved intentionally — no behavior change |
| 9 | `SQLService` instantiated multiple times | Not fixed — caching refactor out of scope |
