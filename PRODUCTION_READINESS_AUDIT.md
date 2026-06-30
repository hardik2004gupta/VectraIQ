# PRODUCTION_READINESS_AUDIT.md — VectraIQ Phase 3.5

**Audit date:** 2026-06-30  
**Auditor:** Principal Staff Software Engineer / Backend Architect  
**Scope:** Full vectraiq/ backend, Dockerfile, docker-compose.yml, pyproject.toml, README  
**Phase:** Pre-Phase 4 gate review

---

## 1. Architecture Review

### Separation of Concerns — 8/10

The three-layer structure (API → AI pipeline → infrastructure services) is clean and consistently applied. Security is correctly modelled as a vertical cross-cut, not a service. The exception hierarchy in `exceptions.py` gives every error a clear home. The observability hooks (`observability.py`) are properly decoupled from business logic.

**Deductions:**  
- `core/graph.py` duplicates intent routing, SQL generation, and RAG orchestration that already live in `ai/rag_service.py`. Two parallel execution paths exist: one through LangGraph nodes, one through the `run_rag()` service. They are not in sync (graph uses its own `sql_service = SQLService()` instance; rag_service has `_sql_service`). A change in SQL logic must be applied in two places.
- `graph.py` `retrieve_rag` node calls `run_rag()` (full RAG pipeline including LLM generation) merely to extract source names, then discards the generated answer. This is architecturally incorrect — the node name says "retrieve" but it runs a full generate cycle.

### Modularity — 9/10

Excellent. Every AI technique (HyDE, CRAG, Self-RAG, Reranking, Sparse Index) is its own file with a clear interface. Adding or replacing any technique requires touching only one file. The cache is properly isolated behind a service class. Storage uses the ABC pattern correctly.

### Dependency Direction — 8/10

Dependencies flow consistently downward: API → security → AI services → cache → config. No upward imports found. The one weakness is that `graph.py` is at `core/` but imports heavily from `ai/` (acceptable) and creates its own module-level `sql_service = SQLService()` while `rag_service.py` has `_sql_service = SQLService()` (two SQLService instances).

### Maintainability — 7/10

Good naming, short focused files, consistent patterns. Main deductions:
- The dual-path execution (LangGraph vs rag_service) makes any change require careful verification in both paths.
- `graph.py` `retrieve_rag` node creates anonymous objects with `type("Chunk", (), {...})()` — a code smell that bypasses the type system.
- `finalize()` in graph.py is an empty `return {}` — dead node that adds no value.

### Scalability — 6/10

Critical blocker:  
- `_build_sparse_index()` in `vector_store.py` scrolls ALL 10,000 Qdrant documents and re-fits the TF-IDF model on **every** sparse or hybrid query. This is not scalable beyond toy load. At 100 concurrent users sending hybrid queries, this becomes a catastrophic bottleneck.
- `get_client()` in `vector_store.py` creates a new `QdrantClient` (new HTTP session) on every `search()`, `hybrid_search()`, `sparse_search()` call.
- No connection pooling for PostgreSQL (psycopg2 `connect()` called per request in auth.py and sql_service.py).
- `_get_checkpointer()` opens a single persistent psycopg v3 connection with no reconnection logic. This connection will go stale after idle timeout.

**Architecture score: 7.6/10**

---

## 2. API Review

### Consistency — 8/10

All error responses now share the `ErrorResponse` envelope. HTTP status codes are used correctly. Auth, query, and admin endpoints follow consistent patterns.

**Inconsistencies found:**

1. **`/admin/cache/clear` returns `dict[str, Any]` but all other endpoints return typed Pydantic models.** The return type annotation says `dict[str, Any]` but the method is not declared with a `response_model`. This means the OpenAPI schema shows no return type for this endpoint.

2. **`/admin/health` returns 200 even when status is "degraded".** Standard practice is to return 503 when any critical dependency is down, so load balancers and uptime monitors can detect failures.

3. **Query endpoint name collision.** The function is named `query_endpoint` in the code but `query` in the original intent. The route is `/query` — acceptable, but the internal function name `query_endpoint` is slightly verbose given the module context.

4. **`confidence` field in `ChatResponse` is hardcoded.** Every RAG path returns `confidence=0.7`, SQL returns `0.9`, hybrid `0.8`. These are magic constants, not computed values. The field exists in the response model but provides no real signal.

### REST Principles — 7/10

- `POST /query/sql/execute` is not a RESTful resource — it's an action on an implicit state machine. Better as `POST /queries/{query_id}/execute` with path parameter. Current design works but violates resource-oriented naming.
- `POST /admin/cache/clear` should arguably be `DELETE /admin/cache` per REST convention.
- No versioning (`/v1/` prefix) — breaking changes in Phase 4 will be painful.

### Authentication — 9/10

JWT HS256 with configurable expiry, bcrypt password hashing (12 rounds), IP-rate-limited auth endpoints, admin role enforcement. Solid. Minor: no token refresh endpoint — users must re-login after expiry.

### Validation — 8/10

Pydantic v2 validators, injection pattern checking, min/max constraints on all fields. The `field_validator` for injection detection is applied at model level (correct). Minor: `AuthRequest.username` allows any character including SQL special characters — no sanitization beyond length.

**API score: 8/10**

---

## 3. AI Pipeline Review

### Hybrid Search — 5/10 ⚠️

Algorithmically correct (dense Qdrant + TF-IDF BM25 + RRF fusion). **Critical flaw:** `_build_sparse_index()` is called on every sparse and hybrid query, re-scrolling 10K documents and re-fitting the TF-IDF model. Latency impact: 5–30 seconds added per hybrid query. This is the single highest-impact performance issue in the entire codebase.

### HyDE — 8/10

Clean implementation. `HyDERetriever` generates N hypothetical answers, embeds them, and deduplicates results by text. Module-level singleton added in Phase 3. The only concern: N=3 means 3 LLM calls + N+1 embedding calls before any retrieval — making HyDE the most expensive retrieval mode.

### ReRanking — 9/10

CrossEncoder loads once via module singleton. Voyage fallback is clean. Thread-safe (no shared mutable state beyond the cached model). Excellent.

### CRAG — 7/10

Logic is correct. When relevance is low, fallback to Tavily. When Tavily key is absent, returns empty chunks silently (the `ValueError` from `search_web` is caught and logged as a warning, returning empty list). This means low-relevance queries with no Tavily key return an empty answer — a silent degradation the user sees as "No results."

Uses stdlib `logging` not loguru — inconsistency with the rest of the codebase.

### Self-RAG — 7/10

Reflection prompt is well-designed with strict scoring criteria. The `reflect_on_answer` function passes the reflection prompt as the **system message** with an **empty user message** — this is unconventional. Most LLM providers accept this, but it could produce unexpected behavior with non-OpenAI providers.

On failure, `ReflectionResult(reflection_score=1.0, needs_regeneration=False)` is returned — meaning failures silently accept the answer. Correct for resilience, but the failure is logged at `ERROR` level inconsistently with other services.

### Text2SQL — 7/10

Good SQL safety (`is_select_only()` with comment stripping and multi-statement detection). Module-level `_sql_service` singleton in `rag_service.py` means schema introspection is cached across calls *when going through rag_service*. However, `graph.py` has its own `sql_service = SQLService()` at module level — this is a **second independent instance** with its own schema cache. The graph and rag_service will each fetch the DB schema independently on their first respective call.

### Caching — 8/10

Five-tier Redis + in-memory LRU. Graceful degradation. Good key design (SHA-256 namespacing). Known limitation: Redis `clear()` only clears in-memory (documented). Solid.

**Minor:** `embedding_service.py` line 35: `return [r for r in results if r is not None]` silently drops entries if any embedding API call partially fails. The caller expects `len(output) == len(input)`.

### LangGraph — 7/10

Human-in-the-loop SQL approval works correctly. `_get_checkpointer()` opens a persistent psycopg v3 connection without:
- Connection pooling
- Reconnection on idle timeout
- Error handling if Postgres is down at import time
- Any max_conn limit

`build_graph()` is called at module import time (`graph = build_graph()`). If PostgreSQL is unreachable at startup, importing `vectraiq.core.graph` raises an exception, crashing the entire application. This makes cold starts fragile.

### Guardrails — 8/10

9-layer security pipeline is architecturally sound. llm-guard for injection + toxicity + PII. Spotlighting correctly tags retrieved context. System prompt prohibits disclosure. `output_validator.py` exists but is never called — it is dead code (audit finding from Phase 0 remains unresolved).

**AI Pipeline score: 7.3/10**

---

## 4. Code Quality Review

### Duplicate Logic — HIGH SEVERITY

**`graph.py` + `rag_service.py` dual-path problem:**  
Both implement intent routing + SQL + RAG independently. `graph.py` calls `run_rag()` from `rag_service.py` for the RAG node but also maintains its own SQL service instance, its own hybrid answer synthesis (`_generate_hybrid_answer`), and its own JSON serializer (`_safe_json_dumps`).

`rag_service.py` has `_run_sql_inline` and `_run_hybrid_inline` that parallel the graph logic.

This is the largest maintainability risk in the codebase. A bug fix or improvement to SQL generation must be verified in both `graph.py` nodes AND `rag_service.py` inline paths.

### Dead Code

| Item | Location | Status |
|---|---|---|
| `output_validator.py` — `validate_with_retry()` | `vectraiq/security/output_validator.py` | Never imported in any production call path |
| `finalize()` node in graph | `vectraiq/core/graph.py:143` | Returns `{}` — empty no-op node |
| `cost_saved_usd` field in GraphState | `vectraiq/core/state.py:47` | Tracked in state but never written or read |
| `cache_hits` field in GraphState | `vectraiq/core/state.py:45` | Allocated but never populated by any node |
| `hypotheses`, `reranked_chunks`, `crag_evaluation`, `web_results` in GraphState | `core/state.py` | All declared in TypedDict but no graph node writes to them |
| `rag_cache_hit`, `sql_cache_hit` in GraphState | `core/state.py` | Never written |
| `chunk_previews` in GraphState | `core/state.py` | Written by `generate_answer` but never read by any subsequent node |

### Oversized/Complex Functions

- `rag_service.py` `run_rag()` orchestrates 7 separate concerns in one function (cache check, intent classification, 3 execution paths, cache write). Well-structured but does a lot.
- `graph.py` `generate_answer()` handles all three intents (sql/hybrid/rag) — the RAG branch calls `run_rag()` again internally, meaning the graph runs a full secondary pipeline.

### Inconsistent Logging Backends

| File | Logger |
|---|---|
| Most vectraiq files | loguru (`from loguru import logger`) |
| `crag.py` | stdlib (`import logging; logger = logging.getLogger(__name__)`) |
| `self_reflective.py` | stdlib |
| `web_search.py` | stdlib |
| `router_service.py` | stdlib |
| `sparse_vector_service.py` | — (no logging) |
| `document_processor.py` | loguru |

The stdlib loggers ARE routed through loguru via `_StdlibHandler`, but they lose the request_id patcher because the patcher only applies to loguru's own logger records.

### Magic Constants

- `confidence` in `ChatResponse`: `0.7` (RAG), `0.9` (SQL), `0.8` (hybrid) — none computed
- `VECTOR_SIZE = 1536` hardcoded in `vector_store.py` — not driven by `settings.embedding_model`
- `_DEFAULT_BASE = ".vectraiq_storage"` in `local.py` — reasonable default but not in config

### Naming

- `_safe_json_default` / `_safe_json_dumps` in `graph.py` are exact duplicates of the serializer in `sql_service.py` — two implementations of the same function in two files
- `SqlExecuteRequest` was renamed to `SqlApprovalRequest` in models.py but the variable name in the test flow still says "execute" — minor naming drift

**Code Quality score: 6.5/10**

---

## 5. Performance Audit

See dedicated `PERFORMANCE_REVIEW.md` for full detail.

**Summary of critical findings:**

| Issue | Severity | Est. Latency Impact |
|---|---|---|
| `_build_sparse_index()` on every hybrid query | CRITICAL | +5–30s per hybrid/sparse request |
| `QdrantClient` created per search call | HIGH | +50–200ms per vector operation |
| psycopg2 `connect()` per request | HIGH | +20–100ms per auth/SQL request |
| `tiktoken` encoding loaded per `count_tokens()` call | MEDIUM | +10–50ms per security check |
| `graph.py` `retrieve_rag` node runs full RAG pipeline for hybrid | HIGH | Doubles LLM cost for hybrid path |
| `psycopg` v3 connection no pooling / no reconnect | MEDIUM | Potential 503 on idle timeout |
| HyDE: 3 LLM calls + 4 embedding calls | LOW-MEDIUM | 3–8s added when HyDE enabled |

**Performance score: 5/10** (unblocked for demo; blocked for production)

---

## 6. Dependency Review

| Package | Status | Notes |
|---|---|---|
| `fastapi` | Required | Core framework |
| `uvicorn[standard]` | Required | ASGI server |
| `pydantic` + `pydantic-settings` | Required | Models + config |
| `openai` | Required | LLM + embeddings |
| `tiktoken` | Required | Token counting |
| `qdrant-client` | Required | Vector DB |
| `psycopg2-binary` | Required | Auth, SQL, seeds |
| `psycopg[binary]` | Required (missing from pyproject.toml!) | LangGraph checkpointer |
| `langgraph` + `langgraph-checkpoint-postgres` | Required | State machine |
| `pyjwt` | Required | Auth |
| `passlib[bcrypt]` | Required | Password hashing |
| `loguru` | Required | Logging |
| `upstash-redis` | Required | Cache |
| `sentence-transformers` | Optional | Local reranker (can use Voyage instead) |
| `voyageai` | Optional | Voyage reranker (can use local instead) |
| `tavily-python` | Optional | Web search fallback |
| `llm-guard` | Optional | Input/output scanning (degraded gracefully if absent) |
| `boto3` | Optional | S3 storage (only needed if `STORAGE_BACKEND=s3`) |
| `docling` | Optional | Document ingestion (only used in seed script) |
| `pypdf` | Optional | PDF parsing (alternative to docling) |
| `python-multipart` | Unused | Required for FastAPI file uploads but `/documents/upload` doesn't exist |
| `pyyaml` | Dev-only | Used in `scripts/data_pipeline/` only |
| `faker` | Dev-only | Used in `scripts/data_pipeline/` only |
| `sklearn` | Implicit | Used in `sparse_vector_service.py` but not declared in pyproject.toml! |

**Critical missing dependency:** `scikit-learn` is used in `sparse_vector_service.py` (`TfidfVectorizer`, `cosine_similarity`) but is NOT in `pyproject.toml`. It is likely installed as a transitive dep of `sentence-transformers`, but this is an undeclared dependency — fragile.

**Critical missing from pyproject.toml:** `psycopg[binary]` — LangGraph checkpointer requires psycopg v3, which is installed in Dockerfile but not in pyproject.toml. Local development from `uv sync` will be broken.

---

## 7. Configuration Review

### Gaps and Issues

1. **`DATABASE_NAME` hardcoded as `adv_rag` in `docker-compose.yml`** — The `POSTGRES_DB: adv_rag` was never updated to `vectraiq` or any new name. Inconsistency with the rebrand.

2. **`LOG_JSON=false` hardcoded in `docker-compose.yml`** — Production should use `true`. This should be an env var from `.env`.

3. **`CORS allow_origins=["*"]` with `allow_credentials=True`** — This is invalid per the CORS spec. When `allow_credentials=True`, the spec forbids wildcard origins. Browsers will reject CORS preflight responses for credentialed requests to a wildcard-origin server. **This will break the Next.js frontend immediately.** Must specify exact origins.

4. **`JWT_SECRET` has no minimum-length validation** — A 1-character secret is accepted. The config validator only warns if empty, but `""` passes Pydantic since the field type is `str`.

5. **`DocumentProcessor` hardcodes `AcceleratorDevice.MPS`** — Apple Silicon GPU acceleration. Will silently fail or error on Linux/Docker (where CUDA is expected, or CPU should be used). The Dockerfile is based on `python:3.12-slim` which is Linux/x86.

6. **No secrets validation at startup** — `_warn_missing_config()` warns but doesn't block. A misconfigured JWT_SECRET means JWTs will be signed with an empty string.

7. **`pyyaml` and `faker` in runtime deps** — Should be dev-only.

8. **Missing `.env.example` verification** — Not read during audit. Should be cross-referenced against all `settings.*` fields.

---

## 8. Security Audit

See dedicated `SECURITY_AUDIT.md` for full analysis.

**Summary of critical findings:**

| Issue | Severity | OWASP LLM # |
|---|---|---|
| SQL approval not user-scoped | HIGH | LLM06 |
| CORS `allow_origins=["*"]` + credentials | HIGH | N/A |
| Empty `JWT_SECRET` accepted | HIGH | N/A |
| `output_validator.py` is dead code (L9 never runs) | MEDIUM | LLM02 |
| Tavily web fallback injects un-validated external content | MEDIUM | LLM02 |
| No HTTPS enforcement in Dockerfile/compose | MEDIUM | N/A |
| No `Strict-Transport-Security` header | LOW | N/A |

**Security score: 6.5/10**

---

## 9. Logging & Observability Review

**Strengths:**
- Request ID propagation via `contextvars` — correct async-safe implementation
- Structured access log per request with status, latency, client IP
- `timed_ai_call()` wraps all LLM calls — Langfuse/OTEL-ready
- Dev vs JSON mode via env var

**Gaps:**

1. **`request_id_var.reset(token)` in `RequestContextMiddleware`** — The `finally` block imports `copy_context` but never uses it. The `reset()` call is correct but the dead import is confusing.

2. **Stdlib loggers (crag, self_reflective, web_search, router_service) lose request_id** — They route through loguru via `_StdlibHandler`, but the patcher that injects `request_id` only applies to loguru-native records. Stdlib records pass through the bridge and print `rid=-` even when a request_id is set.

3. **No latency histogram or p95/p99 tracking** — The observability hooks log per-call latency but there's no aggregation. Post-Phase 4 this should be connected to metrics.

4. **No Sentry/error tracking integration** — Unhandled exceptions go to logs only. In production, these should also go to an error tracking service.

5. **`search_web` (Tavily) call is not wrapped in `timed_ai_call`** — Tavily latency is untracked.

**Observability score: 7/10**

---

## 10. Testing Audit

**Current state:** Zero tests. The `tests/` directory referenced in `pyproject.toml` and `README.md` does not exist.

**Critical missing tests:**

| Area | Test Type | Priority |
|---|---|---|
| `is_select_only()` SQL validator | Unit | CRITICAL |
| `_check_injection()` pattern validator | Unit | CRITICAL |
| JWT encode/decode roundtrip | Unit | CRITICAL |
| `hash_password` / `verify_password` | Unit | CRITICAL |
| `QueryCacheService` hit/miss/TTL | Unit | HIGH |
| `truncate_to_token_limit` edge cases | Unit | HIGH |
| `LocalStorage` path traversal protection | Unit | HIGH |
| `POST /auth/register` duplicate username | Integration | HIGH |
| `POST /auth/login` wrong password | Integration | HIGH |
| `POST /query` rate limit enforcement | Integration | HIGH |
| `POST /query` injection blocking | Integration | HIGH |
| `fuse_rrf()` RRF fusion correctness | Unit | MEDIUM |
| `classify_intent()` fallback to "rag" on failure | Unit | MEDIUM |
| CRAG with low relevance → web fallback | Unit | MEDIUM |
| Self-RAG reflection loop exit conditions | Unit | MEDIUM |

**Testing score: 1/10** (no tests exist)

---

## 11. Documentation Audit

| Document | Status | Issue |
|---|---|---|
| `README.md` | Stale | References `app.main:app`, `app/` directory structure, `/documents/upload` endpoint (missing), `tests/unit/` (missing), AWS ECS/CloudFormation (not implemented) |
| `AUDIT_REPORT.md` | Current | Phase 0 audit — still accurate |
| `CLAUDE.md` | Slightly stale | References Phase 0/1/2 completion; Phase 3 not reflected |
| `ARCHITECTURE_V2.md` | Current (Phase 1) | Target architecture — not yet fully implemented |
| Phase 2 docs | Current | Accurate for Phase 2 state |
| Phase 3 docs | Current | Accurate for Phase 3 |
| Docstrings | Partial | Most public functions and classes have docstrings. AI service files (`crag.py`, `hyde.py`, `self_reflective.py`) have minimal docstrings. |
| API docs (OpenAPI) | Good | Swagger/ReDoc auto-generated. All endpoints have `summary` and `description`. Error responses documented. |
| Environment docs | Stale | `.env.example` not read but README references it with old variable names (`S3_CACHE_BUCKET=adv-rag-cache`). |

**Documentation score: 5/10**

---

## 12. Deployment Audit

### Dockerfile — BROKEN ⛔

```dockerfile
COPY app/ ./app/        # Line 22 — copies OLD package, not vectraiq/
```

The Dockerfile was never updated after Phase 2. It copies the `app/` directory, not `vectraiq/`. The `CMD` runs `scripts/serve.py` which now references `vectraiq.main:app` — but `vectraiq/` is never copied into the image. **The Docker image as written will fail to start.**

Also:
- `AcceleratorDevice.MPS` in `DocumentProcessor` will fail on Linux
- No healthcheck directive on the app container
- No non-root user (running as root is a container security risk)
- No `psycopg[binary]` in pyproject.toml means the LangGraph checkpointer breaks in local installs

### docker-compose.yml — PARTIALLY BROKEN

```yaml
volumes:
  - ./app:/app/app    # Line 53 — mounts OLD app/ directory
```

The volume mount still points to `./app`. This means local dev with `docker compose up` will not pick up changes to `vectraiq/`.

Also:
- `LOG_JSON=false` hardcoded — should be `${LOG_JSON:-false}`
- No healthcheck on the `app` service
- Database name still `adv_rag` (not updated after rebrand)

### Can this backend deploy today?

**No.** The Docker image build will succeed (it copies `app/`) but the application will fail to start because `CMD ["python", "scripts/serve.py"]` runs `vectraiq.main:app` which is not in the image.

**Deployment score: 3/10** (infrastructure YAML must be updated before any deploy)

---

## 13. Frontend Readiness

| Requirement | Status | Notes |
|---|---|---|
| Stable APIs | ✅ | 7 endpoints, stable shapes |
| Consistent error schema | ✅ | `ErrorResponse` envelope |
| Auth flow (JWT bearer) | ✅ | Register + login + token refresh (missing) |
| CORS | ❌ | `allow_origins=["*"]` + credentials will fail in browser |
| OpenAPI schema | ✅ | `/docs`, `/redoc`, `/openapi.json` |
| Streaming | ❌ | No SSE/WebSocket streaming — long waits with no feedback |
| Pagination | N/A | No list endpoints currently |
| Filtering | N/A | Not applicable yet |
| File uploads | ❌ | `/documents/upload` endpoint is missing |
| Token response includes `expires_in` | ✅ | Phase 3 addition |
| Request correlation ID | ✅ | `X-Request-ID` header + `request_id` in response body |
| SQL approval flow | ✅ | `pending_sql` block → `/query/sql/execute` |

**Frontend Readiness: Partially ready. CORS and streaming are blockers.**

---

## 14. Technical Debt

See dedicated `TECHNICAL_DEBT_REPORT.md` for full register.

**Critical:** Dockerfile copies wrong directory (blocking)  
**Critical:** `_build_sparse_index()` on every hybrid query (performance)  
**Critical:** CORS wildcard + credentials (frontend blocker)  
**High:** Dual execution paths (LangGraph vs rag_service)  
**High:** No tests  
**High:** `psycopg[binary]` missing from pyproject.toml  
**High:** SQL approval not user-scoped  

---

## 15. Production Readiness Scores

| Dimension | Score | Notes |
|---|---|---|
| Architecture | 8/10 | Clean layering, good DI; dual-path weakness |
| Maintainability | 7/10 | Good naming, focused files; dual-path debt |
| Performance | 5/10 | Sparse index blocker; Qdrant client per call |
| Security | 7/10 | Strong pipeline; CORS wildcard & SQL approval scope gap |
| Developer Experience | 6/10 | Good logging, observability; zero tests; stale README |
| Documentation | 6/10 | Good API docs; stale README; no env doc |
| Testing | 1/10 | Zero tests exist |
| Deployment | 3/10 | Dockerfile broken; compose broken |
| Scalability | 5/10 | Sparse index + no connection pooling are hard blockers |
| **Overall Production Readiness** | **5.3/10** | Not yet ready for public deployment |

---

## 16. Final Recommendations

### What is excellent?

- **AI pipeline architecture**: Clean, modular, each technique isolated, singleton management added in Phase 3
- **Security pipeline**: 9-layer design is genuinely thoughtful and well-implemented
- **Exception hierarchy**: `exceptions.py` with typed domain errors is production-grade
- **Structured logging**: Request ID correlation, loguru with JSON mode, observability hooks
- **Cache design**: 5-tier Redis+memory with graceful degradation
- **LangGraph integration**: Human-in-the-loop SQL approval is correctly implemented
- **Pydantic models**: Clean request/response schemas with injection checking
- **Error handling**: Centralized handlers, consistent `ErrorResponse` envelope

### What still needs work?

1. **Dockerfile and docker-compose must be fixed before ANY deployment** (copies wrong directory)
2. **`_build_sparse_index()` must be cached** (module-level singleton with rebuild trigger)
3. **CORS `allow_origins=["*"]` must be replaced with explicit origins before any frontend work**
4. **`psycopg[binary]` must be added to `pyproject.toml`**
5. **Tests must be written** — at minimum for security validators, SQL safety, and auth
6. **SQL approval must be user-scoped** to prevent cross-user thread resumption
7. **QdrantClient should be a module-level singleton**
8. **README must be rewritten** to reflect the vectraiq package rename
9. **`output_validator.py` should be wired in or removed**
10. **Streaming endpoint (`/query/stream`) needed** before frontend development

### What should never be rewritten?

- The LangGraph state machine topology — human-in-the-loop SQL approval design is correct
- The 5-tier cache architecture — well-designed and working
- The security pipeline layer order — each layer serves a distinct purpose
- The CRAG + Self-RAG combination — algorithmically sound
- The exception hierarchy — immediately production-grade

### What should be simplified later?

- The dual execution path (LangGraph vs rag_service inline) — one should eventually be removed
- `GraphState` TypedDict — half the fields are declared but never written; prune to actual used fields
- `finalize()` node in graph — empty no-op; remove
- The document ingestion pipeline — `DocumentProcessor` with MPS hardcoding needs to be configurable

### Is the backend ready for frontend development?

**Conditionally yes.** Fix these 3 items first:
1. **CORS** — `allow_origins=["*"]` with credentials will block all browser requests
2. **Token refresh** — frontend needs a way to refresh tokens without re-login
3. **Streaming** — 10-30 second silent waits are unacceptable in a chat UI

The API shape, auth flow, and error envelopes are stable enough to build against.

### Is the backend ready for public deployment?

**No.** The Dockerfile is broken. Sparse index performance is unacceptable under load. No tests. CORS is misconfigured.

### Would you approve this repository for production?

**Not yet.** This is a well-architected, thoughtfully-designed system with genuine production-quality patterns in security, caching, and AI pipeline design. The blockers are:
1. Dockerfile/compose broken (blocking)
2. Performance (sparse index — blocking at scale)
3. Testing (no tests — blocking for any serious service)
4. CORS (blocking for frontend)

Fix these 4 areas and this backend is deployable. It is absolutely ready for frontend development once CORS is corrected.
