# TECHNICAL_DEBT_REPORT.md — VectraIQ Phase 3.5

**Audit date:** 2026-06-30  
**Classification:** Critical / High / Medium / Low  
**Total debt items:** 28

---

## Critical — Blockers for Deployment

These items will cause the system to fail to deploy, fail to start, or expose serious security holes. They MUST be fixed before any production release.

---

### TD-001 — Dockerfile Copies Wrong Directory
**File:** `Dockerfile` line ~22  
**Severity:** CRITICAL — container fails to start  

```dockerfile
COPY app/ ./app/    # Copies OLD app/ package
# vectraiq/ is never copied into the Docker image
```

Phase 2 renamed the authoritative Python package from `app/` to `vectraiq/`. The Dockerfile was not updated. The `CMD` is `["python", "scripts/serve.py"]`, which internally runs `uvicorn vectraiq.main:app`. But `vectraiq/` does not exist inside the container — `ImportError` at startup.

**Fix:** Replace `COPY app/ ./app/` with `COPY vectraiq/ ./vectraiq/`. Also add `COPY scripts/ ./scripts/` if not already present.

---

### TD-002 — docker-compose Volume Mounts Wrong Directory
**File:** `docker-compose.yml`  
**Severity:** CRITICAL — local dev mode broken  

```yaml
volumes:
  - ./app:/app/app    # mounts OLD app/ directory
```

Local development with `docker compose up` will not pick up any changes made to `vectraiq/`.

**Fix:** `- ./vectraiq:/app/vectraiq`

---

### TD-003 — `psycopg[binary]` Missing from `pyproject.toml`
**File:** `pyproject.toml`  
**Severity:** CRITICAL — LangGraph checkpointer broken on local install  

`psycopg[binary]` (v3) is required by LangGraph's `PostgresSaver`. It is installed in the Dockerfile via a separate `RUN uv pip install 'psycopg[binary]'` command but is NOT declared as a dependency in `pyproject.toml`. 

Running `uv sync` (the documented dev setup command) will NOT install psycopg v3. The first `import vectraiq.core.graph` will fail with `ModuleNotFoundError: No module named 'psycopg'`.

**Fix:** Add `"psycopg[binary]>=3.1"` to `[project.dependencies]` in `pyproject.toml`.

---

### TD-004 — CORS Wildcard + Credentials
**File:** `vectraiq/main.py`  
**Severity:** CRITICAL — all browser requests from frontend will be rejected  

```python
CORSMiddleware(allow_origins=["*"], allow_credentials=True, ...)
```

The CORS spec forbids `Access-Control-Allow-Origin: *` when credentials are involved. Every JWT-authenticated request from the Next.js frontend will fail with a CORS preflight error.

**Fix:** Replace `["*"]` with `[settings.frontend_origin]` where `FRONTEND_ORIGIN` is an env var (e.g., `http://localhost:3000` for dev, `https://app.vectraiq.io` for prod).

---

### TD-005 — SQL Approval Not User-Scoped
**File:** `vectraiq/api/query.py` — `sql_execute` endpoint  
**Severity:** CRITICAL — authorization bypass  

Any authenticated user can resume any pending SQL thread by providing any `query_id`. The endpoint does not verify that the thread was initiated by the requesting user.

**Fix:** Store `username` in the LangGraph thread state. In `sql_execute`, retrieve the thread state, verify `state["user_id"] == user.username`, raise `AuthorizationError` if mismatch.

---

## High — Must Fix Before Public Release

These items are not deployment-blockers but create significant security, reliability, or maintainability problems.

---

### TD-006 — `JWT_SECRET` Accepts Empty or Weak Values
**File:** `vectraiq/config.py`  
**Why:** A JWT signed with an empty or short secret is trivially forgeable. `_warn_missing_config()` warns but allows startup to proceed.  
**Fix:** `@field_validator("jwt_secret") def validate_jwt_secret(cls, v): assert len(v) >= 32, "JWT_SECRET must be at least 32 characters"`

---

### TD-007 — Zero Tests
**Files:** `tests/` — does not exist  
**Why:** No test coverage for security validators, SQL safety, auth flows, or cache behavior. A change to `is_select_only()` or `_check_injection()` could silently remove safety checks.  
**Minimum required:** Unit tests for `is_select_only()`, `_check_injection()`, `hash_password`/`verify_password`, and `QueryCacheService` hit/miss logic.

---

### TD-008 — Dual Execution Paths
**Files:** `vectraiq/ai/rag_service.py` + `vectraiq/core/graph.py`  
**Why:** Both files implement intent routing, RAG retrieval, SQL generation, and hybrid synthesis. A bug fix to SQL logic must be applied in two places. The hybrid synthesis in `graph.py` does NOT use the hardened system prompt from `system_prompt.py` — a security policy difference between the two paths that is invisible to reviewers.  
**Fix:** `graph.py` nodes should call service functions from `rag_service.py` and `sql_service.py` rather than implementing their own logic. The `retrieve_rag` node should call a retrieval-only function, not `run_rag()`.

---

### TD-009 — `_build_sparse_index()` Performance Bug
**File:** `vectraiq/ai/vector_store.py`  
**Why:** Re-scrolls 10,000 Qdrant documents and re-fits TF-IDF on every sparse or hybrid query. Makes hybrid search 5–30x slower than necessary. Unacceptable under any real load.  
**Fix:** Cache as module-level singleton with a TTL-based rebuild.

---

### TD-010 — `output_validator.py` Is Dead Code
**File:** `vectraiq/security/output_validator.py`  
**Why:** The function `validate_with_retry()` is exported from `security/__init__.py` but never called anywhere in the production request path. The README lists this as Layer 9 of the security pipeline, but it is not wired in. This creates a false sense of security.  
**Fix:** Either wire it into `api/query.py` after `moderate_and_redact()`, or formally remove it and update all documentation.

---

### TD-011 — `local_storage.py` Is Incomplete
**File:** `vectraiq/storage/local_storage.py`  
**Why:** The file is a stub (1-line or near-empty). `DocCacheService(storage_backend="local")` will raise on any file operation. The default storage backend in config is `local`, so all document caching is broken by default.  
**Fix:** Implement `save_file(path, content)`, `load_file(path)`, `file_exists(path)` using `pathlib.Path`. Or change default to `s3` and document that local storage is not supported.

---

### TD-012 — `scikit-learn` Is an Undeclared Dependency
**File:** `pyproject.toml`  
**Why:** `vectraiq/ai/sparse_vector_service.py` imports `TfidfVectorizer` and `cosine_similarity` from sklearn. `scikit-learn` is not in `pyproject.toml`. It happens to be installed transitively by `sentence-transformers`, but this is fragile — if `sentence-transformers` is ever replaced or its transitive deps change, sparse search breaks silently.  
**Fix:** Add `"scikit-learn>=1.4"` to `[project.dependencies]`.

---

### TD-013 — `graph.py` `retrieve_rag` Uses Anonymous Object Hack
**File:** `vectraiq/core/graph.py`  
**Why:**
```python
type("Chunk", (), {"text": src, "source": src, "score": 1.0})()
```
This creates a fake chunk with `text == source == document_name` and `score=1.0`. The actual retrieved text is discarded. The spotlighted context for hybrid queries contains only document names, not document content. This causes the hybrid answer synthesis to operate on essentially empty context.  
**Fix:** `retrieve_rag` should call a retrieval-only function that returns actual `RetrievedChunk` objects with their text content.

---

### TD-014 — `_generate_hybrid_answer` Does Not Use Hardened System Prompt
**File:** `vectraiq/core/graph.py`  
**Why:** The hardened system prompt (behavioral guardrails + domain restrictions) from `vectraiq/security/system_prompt.py` is only applied in the `rag_service.py` path. The graph's hybrid answer node uses a simple f-string prompt:
```python
system_prompt = "You are a helpful assistant..."  # No domain restrictions
```
This means a hybrid query going through LangGraph bypasses the security policy.  
**Fix:** Import and use `get_hardened_system_prompt()` from `system_prompt.py` in `_generate_hybrid_answer`.

---

### TD-015 — `DocumentProcessor` Hardcodes `AcceleratorDevice.MPS`
**File:** `vectraiq/ai/document_processor.py`  
**Why:** `AcceleratorDevice.MPS` is Apple Silicon GPU. The Dockerfile is `python:3.12-slim` (Linux). Running document ingestion in Docker will fail with a hardware mismatch error.  
**Fix:** Detect platform: `device = AcceleratorDevice.MPS if platform.system() == "Darwin" else AcceleratorDevice.CPU`

---

### TD-016 — README Is Completely Stale
**File:** `README.md`  
**Why:** Still references `app.main:app` (changed to `vectraiq.main:app`), "ADV RAG" project name, `app/` directory structure, `/documents/upload` endpoint (doesn't exist), `tests/unit/` directory (doesn't exist), AWS ECS deployment (not implemented), `S3_CACHE_BUCKET=adv-rag-cache` (old bucket name). A new developer following the README would fail to run the project.  
**Fix:** Full README rewrite reflecting vectraiq package, Phase 2–3 architecture, correct commands.

---

## Medium — Meaningful Quality Issues

### TD-017 — Three SQLService Instances (Schema Cache Miss)
**Why:** `rag_service.py` has `_sql_service = SQLService()`, `graph.py` has `sql_service = SQLService()`. Each has its own `_schema_context` cache. Schema introspection runs twice on startup and two caches are maintained.  
**Fix:** Export a shared `get_sql_service()` factory or make `SQLService` a true singleton.

---

### TD-018 — Two OpenAI Client Instances
**Why:** `llm_service.py` and `embedding_service.py` each create `OpenAI(...)` module-level singletons. Two HTTP connection pools are maintained.  
**Fix:** Share one `OpenAI` client via a `get_openai_client()` getter in a shared module.

---

### TD-019 — `QdrantClient` Created Per Call
**Why:** `get_client()` in `vector_store.py` creates a new `QdrantClient` (new httpx session) on every search call.  
**Fix:** Module-level singleton.

---

### TD-020 — Stdlib Logging in AI Files
**Why:** `crag.py`, `self_reflective.py`, `web_search.py`, `router_service.py` use stdlib `logging`. These log lines appear in the structured log stream (routed through `_StdlibHandler`) but without `request_id` context — the patcher applies only to loguru-native records.  
**Fix:** Replace `import logging; logger = logging.getLogger(__name__)` with `from loguru import logger`.

---

### TD-021 — Unused GraphState Fields (9 Dead Fields)
**Why:** `cache_hits`, `cost_saved_usd`, `hypotheses`, `reranked_chunks`, `crag_evaluation`, `web_results`, `rag_cache_hit`, `sql_cache_hit`, `chunk_previews` are declared in `GraphState` TypedDict but never written by any node.  
**Fix:** Remove from `GraphState` or actually populate them.

---

### TD-022 — `admin/health` Returns 200 When Degraded
**Why:** The health endpoint returns `{"status": "degraded"}` with HTTP 200. Load balancers, uptime monitors, and Kubernetes liveness probes all interpret 200 as healthy. A degraded backend looks healthy to infrastructure.  
**Fix:** Return HTTP 503 when `status == "degraded"`.

---

### TD-023 — No SQL Row Limit
**Why:** Generated SQL has no `LIMIT` clause enforced. An LLM-generated `SELECT * FROM large_table` could return millions of rows, causing memory exhaustion.  
**Fix:** `sql_service.execute_sql()` should append `LIMIT 1000` if the SQL doesn't already contain a LIMIT clause.

---

### TD-024 — `dev`/`script`-only packages in Core Dependencies
**Why:** `faker`, `pyyaml`, `pypdf`, `python-multipart` are in `[project.dependencies]` but are only used in seed scripts and data pipeline tools (or not at all, in the case of `python-multipart`).  
**Impact:** All production installs download and install these packages unnecessarily.  
**Fix:** Move to `[project.optional-dependencies.dev]` or `[tool.uv.dev-dependencies]`.

---

### TD-025 — `finalize` Node in LangGraph Is a No-Op
**Why:** `def finalize(state): return {}` — this node does nothing. It is the terminal node of the graph.  
**Fix:** Remove the node and connect preceding nodes directly to `END`.

---

### TD-026 — `docker-compose.yml` Database Name Not Updated
**Why:** `POSTGRES_DB: adv_rag` — the old database name was not updated to `vectraiq` during rebrand. The `DATABASE_URL` in the app may reference `adv_rag` while the DB container creates database named `adv_rag`. This is consistent (both use the old name) but is stale and confusing.  
**Fix:** Decide on the database name (suggest `vectraiq`), update both `docker-compose.yml` and `.env.example`.

---

### TD-027 — Stale `_DOCUMENT_HINTS` in Router Service
**Why:** Contains ML paper benchmarks (`gsm8k`, `humaneval`) and ML model names (`llada`) from a previous project. Could cause intent misclassification if a K8s query happens to contain these strings.  
**Fix:** Clear `_DOCUMENT_HINTS` or replace with K8s-relevant hints.

---

## Low — Minor Polish

### TD-028 — `confidence` Field Is Hardcoded
**Why:** `confidence: float = 0.7 / 0.8 / 0.9` depending on intent. Not computed from retrieval scores or reflection output.  
**Fix:** Compute from `ReflectionResult.reflection_score` if Self-RAG is enabled; from CRAG evaluation score if CRAG is enabled; fall back to a default based on cache_hit status.

---

## Debt Summary by Priority

| Priority | Count | Items |
|---|---|---|
| Critical (deploy blockers) | 5 | TD-001 through TD-005 |
| High (pre-release) | 11 | TD-006 through TD-016 |
| Medium (quality) | 11 | TD-017 through TD-027 |
| Low (polish) | 1 | TD-028 |
| **Total** | **28** | |

---

## Debt Payoff Order for Phase 4 Prep

If starting Phase 4 (Next.js frontend) immediately, fix in this order:

1. **TD-004** (CORS) — frontend cannot make any API calls without this
2. **TD-001, TD-002** (Dockerfile/compose) — needed for any container-based testing
3. **TD-003** (psycopg dependency) — needed for local dev of anyone new to the project
4. **TD-009** (sparse index cache) — needed before any performance testing
5. **TD-005** (SQL user-scoping) — security fix, simple to implement
6. **TD-014** (hardened system prompt in graph hybrid path) — security consistency
7. **TD-007** (write tests) — ongoing, should be started in parallel with Phase 4
8. **TD-016** (README) — needed before open-sourcing or onboarding

The remaining items (TD-008 dual-path, TD-011 local storage, TD-012 sklearn declaration) are important but can wait for a cleanup sprint after Phase 4 ships.
