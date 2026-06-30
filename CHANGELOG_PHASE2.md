# CHANGELOG_PHASE2.md — VectraIQ Phase 2

## [2.0.0] — 2026-06-30

### Package Restructuring

- **Renamed** Python package `app` → `vectraiq`
- **Renamed** project in `pyproject.toml`: `adv-rag` → `vectraiq`
- **Bumped** version: `0.1.0` → `2.0.0`
- **Reorganized** `app/services/` into:
  - `vectraiq/ai/` — all AI pipeline services (LLM, embedding, RAG, CRAG, HyDE, Self-RAG, reranking, SQL, routing, document processing, web search, vector store, sparse index)
  - `vectraiq/cache/` — caching services (query cache, document cache)
- **Renamed** storage files:
  - `storage_backend.py` → `storage/backend.py`
  - `local_storage.py` → `storage/local.py`
  - `s3_storage.py` → `storage/s3.py`
- **Updated** all entry points: `scripts/serve.py`, `scripts/seed_db.py`, `eval/invokers.py`, `eval/ragas_adapter.py`, `Makefile`

### Bug Fixes

- **Fixed** `local_storage.py` was empty (1-line stub): implemented full `LocalStorage` class in `vectraiq/storage/local.py` with path traversal protection using `Path.resolve()` prefix checking
- **Fixed** IPv4 addresses being redacted in PII scan: removed IPv4 pattern from `vectraiq/security/content_moderation.py` — IP addresses are operational data essential for Kubernetes networking answers
- **Fixed** rate limiter crashing with 500 when Redis unavailable: added `except Exception` handler with `logger.warning` and allow-through in `vectraiq/middleware/rate_limiter.py`
- **Fixed** token budget crashing with 500 when Redis unavailable: added `except Exception` handler with `logger.warning` and allow-through in `vectraiq/security/token_budget.py`
- **Fixed** untyped `dict` auth body: added `AuthBody(BaseModel)` Pydantic model in `vectraiq/api/auth.py`
- **Fixed** `is_select_only()` did not strip SQL comments before checking: now strips `--` and `/* */` blocks before analysis; also rejects multi-statement SQL (`;` followed by non-whitespace)

### Code Quality

- **Removed** stale `_DOCUMENT_HINTS` from `vectraiq/ai/router_service.py` — contained ML paper terms (`gsm8k`, `humaneval`, `qkv`, `llada`, `elastic-cache`) with no relation to the K8s domain
- **Removed** misleading alias `run_rag_with_trace_no_cache = run_rag_with_trace` from `vectraiq/ai/rag_service.py` — was an identity alias, not a different code path
- **Removed** dead Vanna configuration fields: `vanna_model`, `vanna_temperature`, `vanna_seed` from `vectraiq/config.py`; replaced with `sql_llm_model`, `sql_temperature`
- **Removed** `vanna[openai,postgres]` from `pyproject.toml` — was a dead dependency
- **Deduplicated** injection validation in `vectraiq/models.py`: extracted shared `_check_injection()` function used by both `ChatRequest` and `QueryRequest`
- **Renamed** `summarize_text()` → `truncate_to_token_limit()` in `vectraiq/security/input_restructuring.py` — the function selects sentences greedily, it does NOT call an LLM
- **Added** module-level `_client = OpenAI(...)` singleton in `vectraiq/ai/llm_service.py` — prevents client instantiation on every call
- **Added** module-level `query_cache = QueryCacheService()` singleton in `vectraiq/cache/query_cache.py` — consistent with usage pattern

### Configuration

- `sql_llm_model` (str, default `"gpt-4o"`) — replaces `vanna_model`
- `sql_temperature` (float, default `0.0`) — replaces `vanna_temperature`

### Breaking Changes (from app/ to vectraiq/)

If you were importing from `app.*`, update to `vectraiq.*`:

```python
# Before
from app.services.rag_service import run_rag_with_trace_no_cache
# After
from vectraiq.ai.rag_service import run_rag_with_trace

# Before
from app.security.input_restructuring import summarize_text
# After
from vectraiq.security.input_restructuring import truncate_to_token_limit

# Before (config)
settings.vanna_model
# After
settings.sql_llm_model
```

### Preserved (no changes)

- All LangGraph nodes, graph topology, interrupt/resume flow
- All AI pipeline algorithms (RAG, HyDE, CRAG, Self-RAG, Hybrid Search, Text2SQL)
- All security layer order and behavior
- All API endpoints and response schemas
- All evaluation harness logic
- `app/` package (preserved as-is, no deletions)
- Database schema and seed data
- Docker and infra configuration
