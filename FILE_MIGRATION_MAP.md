# VectraIQ v2 — File Migration Map
**Version:** 2.0  
**Status:** Design Phase  

Decision key: **KEEP** · **MOVE** · **MERGE** · **SPLIT** · **REFACTOR** · **DELETE**

---

## Legend

| Decision | Meaning |
|---|---|
| **KEEP** | Copy as-is to the v2 path. May need minor path updates. |
| **MOVE** | Same file, new location in the monorepo structure. |
| **MERGE** | Content from multiple v1 files becomes one v2 file. |
| **SPLIT** | One v1 file becomes multiple smaller v2 files. |
| **REFACTOR** | Significant rewrite needed; logic is kept but structure changes. |
| **DELETE** | Do not carry forward. Either unused, broken, or replaced. |

---

## Root-Level Files

| v1 Path | Decision | v2 Path | Reason |
|---|---|---|---|
| `pyproject.toml` | REFACTOR | `pyproject.toml` (monorepo root) | Add psycopg[binary], remove Vanna, add dev/test groups, update testpaths |
| `Makefile` | REFACTOR | `Makefile` | Fix broken targets (scripts/data_pipeline/run_all.sh doesn't exist), add new targets (migrate, seed, lint, test-e2e) |
| `Dockerfile` | REFACTOR | `apps/api/Dockerfile` | Move to monorepo; fix psycopg[binary] install; non-root user; multi-stage build |
| `docker-compose.yml` | REFACTOR | `docker-compose.yml` | Add local Redis service; add web service; fix volume names; add --reload for api |
| `.env.example` | REFACTOR | `.env.example` | Add all new variables; remove placeholder JWT_SECRET warning note |
| `.gitignore` | KEEP | `.gitignore` | Already correct |
| `README.md` | REFACTOR | `README.md` | Rebrand to VectraIQ; update architecture description; link to docs/ |
| `AUDIT_REPORT.md` | KEEP | `docs/internal/AUDIT_REPORT.md` | Archive of v1 analysis |
| `CLAUDE.md` | REFACTOR | `CLAUDE.md` | Update after each phase; track v2 progress |

---

## app/main.py

| v1 Path | Decision | v2 Path | Reason |
|---|---|---|---|
| `app/main.py` | REFACTOR | `apps/api/src/main.py` | Add lifespan events for singleton init; add CORS; add middleware stack in correct order; version prefix |

### v1 Problems
- No lifespan events (graph built at import time)
- No CORS configuration
- No middleware registration

### v2 Requirements
```python
# apps/api/src/main.py
@asynccontextmanager
async def lifespan(app: FastAPI):
    await startup()   # build all singletons, run pre-flight checks
    yield
    await shutdown()  # graceful close of pools

app = FastAPI(title="VectraIQ API", version="2.0.0", lifespan=lifespan)
app.include_router(auth_router, prefix="/api/v1/auth")
app.include_router(query_router, prefix="/api/v1/query")
app.include_router(documents_router, prefix="/api/v1/documents")
app.include_router(admin_router, prefix="/api/v1/admin")
```

---

## app/config.py

| v1 Path | Decision | v2 Path | Reason |
|---|---|---|---|
| `app/config.py` | REFACTOR | `apps/api/src/core/settings.py` | Remove Vanna settings; add JWT_SECRET validator (≥32 chars); add all new env var fields; use `@model_validator` for cross-field checks |

---

## app/models.py

| v1 Path | Decision | v2 Path | Reason |
|---|---|---|---|
| `app/models.py` | SPLIT | `apps/api/src/api/v1/schemas/` | Split into `query.py`, `auth.py`, `documents.py`, `analytics.py` |

### v1 Problems
- Duplicate injection validators on `ChatRequest` and `QueryRequest`
- Mixed response models for different domains in one file

---

## app/core/

| v1 Path | Decision | v2 Path | Reason |
|---|---|---|---|
| `app/core/graph.py` | REFACTOR | `apps/api/src/ai/graph/graph.py` | Remove duplicate routing/retrieval logic (ADR-002); keep only state transitions + SQL interrupt; 10 nodes replacing 7 |
| `app/core/state.py` | REFACTOR | `apps/api/src/ai/graph/state.py` | Remove 8 unpopulated fields; add `user_id` for SQL approval scoping; minimize to 20 fields, all used |

---

## app/api/

| v1 Path | Decision | v2 Path | Reason |
|---|---|---|---|
| `app/api/query.py` | REFACTOR | `apps/api/src/api/v1/routers/query.py` | Add user-scoped SQL approval (validate thread belongs to requesting user); add streaming endpoint; delegate to QueryUseCase |
| `app/api/auth.py` | REFACTOR | `apps/api/src/api/v1/routers/auth.py` | Replace untyped `dict` body with Pydantic models; use async psycopg v3; use connection pool |
| `app/api/admin.py` | REFACTOR | `apps/api/src/api/v1/routers/admin.py` | Fix cache clear (Redis tier is a no-op in v1); cache stats should include Redis hit counts |

---

## app/middleware/

| v1 Path | Decision | v2 Path | Reason |
|---|---|---|---|
| `app/middleware/auth.py` | REFACTOR | `apps/api/src/middleware/auth.py` | Replace direct bcrypt import with passlib abstraction; add role extraction from JWT claims |
| `app/middleware/rate_limiter.py` | REFACTOR | `apps/api/src/middleware/rate_limiter.py` | Add graceful degradation: if Redis down, allow request (log warning, don't fail open on security-critical paths) |

---

## app/services/

| v1 Path | Decision | v2 Path | Reason |
|---|---|---|---|
| `app/services/rag_service.py` | SPLIT | `apps/api/src/application/use_cases/query_use_case.py` | Remove duplicate `_run_sql_inline` and `_run_hybrid_inline`; duplicate intent classification removed; becomes thin orchestrator delegating to AI modules |
| `app/services/router_service.py` | REFACTOR | `apps/api/src/ai/router/intent_classifier.py` | Remove irrelevant `_DOCUMENT_HINTS` (ML paper terms have no business in a K8s SRE tool); replace with domain-agnostic routing prompt |
| `app/services/llm_service.py` | REFACTOR | `apps/api/src/infrastructure/providers/llm_provider.py` | Wrap in repository interface; switch to async OpenAI client; separate `generate()` and `generate_json()` with proper `response_format={"type":"json_object"}` on JSON method |
| `app/services/vector_store.py` | REFACTOR | `apps/api/src/ai/retriever/sparse_retriever.py` + `dense_retriever.py` | CRITICAL: `_build_sparse_index()` must NOT scroll 10,000 docs per query; extract to singleton SparseIndex refreshed in background |
| `app/services/hyde.py` | MOVE | `apps/api/src/ai/retriever/hyde_retriever.py` | Logic is sound; clean up type annotations |
| `app/services/crag.py` | MOVE | `apps/api/src/ai/reasoner/crag.py` | Clean implementation; minor refactor for new module interfaces |
| `app/services/reranking.py` | REFACTOR | `apps/api/src/ai/reranker/cross_encoder.py` | CRITICAL: must be singleton; `Reranker()` instantiated per-request reloads model each time |
| `app/services/self_reflective.py` | MOVE | `apps/api/src/ai/reasoner/self_rag.py` | Logic is sound; remove up to 6 LLM calls in worst case by adding per-call token budget guard |
| `app/services/sql_service.py` | REFACTOR | `apps/api/src/ai/sql/sql_generator.py` + `apps/api/src/ai/sql/schema_inspector.py` | `SQLService` must be singleton to preserve schema cache; split schema inspection from SQL generation |
| `app/services/embedding_service.py` | MOVE | `apps/api/src/ai/embedding/embedding_service.py` | Already well-designed; minor interface cleanup |
| `app/services/sparse_vector_service.py` | REFACTOR | `apps/api/src/ai/retriever/sparse_retriever.py` | Fix RRF key: use content hash not raw `chunk.text` (prevents key collision on text with special chars) |
| `app/services/query_cache_service.py` | REFACTOR | `apps/api/src/infrastructure/cache/cache_repository.py` | Fix `clear()` no-op for Redis tier; implement SCAN + DEL in batches; stats must read from Redis, not in-memory |
| `app/services/doc_cache_service.py` | REFACTOR | `apps/api/src/infrastructure/cache/doc_cache.py` | Fix dependency on broken `local_storage.py`; use StorageRepository interface |
| `app/services/web_search.py` | MOVE | `apps/api/src/infrastructure/providers/web_search_provider.py` | Clean implementation; wrap in provider interface |

---

## app/security/

| v1 Path | Decision | v2 Path | Reason |
|---|---|---|---|
| `app/security/content_moderation.py` | REFACTOR | `apps/api/src/ai/security/pii_redactor.py` | CRITICAL: v1 redacts IP addresses, breaking Kubernetes networking answers; v2 must NOT redact IPv4/IPv6 patterns |
| `app/security/input_guard.py` | MOVE | `apps/api/src/ai/security/input_guard.py` | Keep graceful degradation; add explicit log on silent failure |
| `app/security/input_restructuring.py` | REFACTOR | `apps/api/src/ai/security/input_restructuring.py` | Rename `summarize_text()` to `truncate_to_token_limit()` — it is greedy sentence selection, NOT LLM summarization; remove misleading name |
| `app/security/output_validator.py` | REFACTOR | `apps/api/src/ai/security/output_guard.py` | CRITICAL: `validate_with_retry()` is dead code in v1 — wire it into the AnswerGenerator output path |
| `app/security/spotlighting.py` | MOVE | `apps/api/src/ai/security/spotlighting.py` | Clean implementation |
| `app/security/system_prompt.py` | REFACTOR | `apps/api/src/ai/security/system_prompt.py` | Remove mandate for JSON output from answer generator (was never enforced via `response_format`); keep K8s SRE content |
| `app/security/token_budget.py` | REFACTOR | `apps/api/src/middleware/token_budget.py` | Add graceful degradation when Redis is down (fail open with warning, not 500 error) |

---

## app/storage/

| v1 Path | Decision | v2 Path | Reason |
|---|---|---|---|
| `app/storage/storage_backend.py` | MOVE | `apps/api/src/infrastructure/storage/storage_repository.py` | Rename ABC to `StorageRepository`; clean interface |
| `app/storage/local_storage.py` | REFACTOR | `apps/api/src/infrastructure/storage/local_storage.py` | CRITICAL BUG: v1 file is empty (1 line). Implement fully: `save()`, `load()`, `delete()`, `exists()`, `list()` using `pathlib.Path` |
| `app/storage/s3_storage.py` | REFACTOR | `apps/api/src/infrastructure/storage/s3_storage.py` + `r2_storage.py` | Keep S3 implementation; add thin R2 subclass that overrides endpoint_url |

---

## scripts/

| v1 Path | Decision | v2 Path | Reason |
|---|---|---|---|
| `scripts/streamlit_app.py` | SPLIT | Phase 1: `scripts/streamlit_app.py` (keep temporarily) → Phase 4: DELETE | Split first: fix broken `/documents/upload` endpoint call; remove hardcoded `agent@demo.local` credentials. Eventually replace with Next.js frontend entirely. |
| `scripts/seed_db.py` | REFACTOR | `scripts/seed_db.py` | Update for v2 schema; use psycopg v3; make idempotent |

---

## eval/

| v1 Path | Decision | v2 Path | Reason |
|---|---|---|---|
| `eval/seed_questions.yaml` | **KEEP — NEVER DELETE** | `eval/seed_questions.yaml` | 40 golden questions are the regression baseline. Deleting this destroys the ability to measure improvement. |
| `eval/profiles.py` | KEEP | `eval/profiles.py` | 7 evaluation profiles are correct and well-designed |
| `eval/run_eval.py` (new) | CREATE | `eval/run_eval.py` | New script to run eval against v2 API endpoints; output RAGAS metrics to `eval/results/` |

---

## seed/

| v1 Path | Decision | v2 Path | Reason |
|---|---|---|---|
| `seed/migrations/001_create_users.sql` | KEEP | `seed/migrations/001_create_users.sql` | Schema is correct |
| `seed/migrations/002_*.sql` (if exists) | KEEP | same | Keep all migrations in sequence |
| `seed/migrations/003_seed_k8s_ops.sql` | KEEP | `seed/migrations/003_seed_k8s_ops.sql` | clusters, nodes, deployments, pods, incidents, alerts, oncall_logs — needed for SQL eval |
| `seed/migrations/004_*.sql` (new) | CREATE | `seed/migrations/004_add_api_features.sql` | Add `conversations` table, `document_chunks` tracking table, `user_token_usage` table |

---

## New Files to Create (No v1 Equivalent)

| v2 Path | Purpose |
|---|---|
| `apps/api/src/core/startup.py` | Pre-flight checks (validate env vars, ping services, build singletons) |
| `apps/api/src/core/dependencies.py` | FastAPI `Depends()` providers for all singletons |
| `apps/api/src/domain/entities/` | Chunk, Document, User, Conversation domain models |
| `apps/api/src/domain/repositories/` | Abstract repository interfaces (ports) |
| `apps/api/src/application/use_cases/document_use_case.py` | Upload, ingest, list, delete documents |
| `apps/api/src/application/use_cases/analytics_use_case.py` | Usage stats, cache stats |
| `apps/api/src/ai/graph/nodes/` | One file per LangGraph node (10 nodes) |
| `apps/web/` | Entire Next.js frontend (new) |
| `.github/workflows/ci.yml` | GitHub Actions CI |
| `.github/workflows/eval.yml` | Weekly eval runner |
| `docs/getting-started.md` | Quick start guide |

---

## Summary Counts

| Decision | Count |
|---|---|
| KEEP | 7 |
| MOVE | 7 |
| REFACTOR | 25 |
| SPLIT | 3 |
| MERGE | 0 |
| DELETE | 0 (streamlit deferred to Phase 4) |
| CREATE (new) | 12+ |

No files are deleted outright in v2. Legacy files are either migrated or replaced gradually. The streamlit app is kept until the Next.js frontend is complete.
