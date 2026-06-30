# VectraIQ Audit Report
**Project:** enterprise-level-rag (to be renamed VectraIQ)  
**Audit Date:** 2026-06-30  
**Auditor:** Principal Staff Engineer / AI Architect  
**Phase:** 0 — Read-Only Analysis  

---

## 1. Executive Summary

### What Does This Project Do?

This is a production-grade AI Knowledge Platform and Kubernetes IT-Operations Copilot. It allows SRE and platform engineers to ask natural-language questions and receive answers from two sources simultaneously: a **vector database** (Qdrant) holding documentation and runbooks, and a **relational database** (PostgreSQL) holding structured operational data. The system routes each question to one of three pipelines — RAG, SQL, or Hybrid — depending on its intent, then applies multiple layers of AI enhancement (HyDE, cross-encoder reranking, CRAG fallback, Self-RAG reflection) and security enforcement before returning a response.

### Overall Architecture

A FastAPI backend exposes three endpoint groups (auth, query, admin). The `/query` endpoint invokes a LangGraph state-machine that orchestrates intent classification → retrieval → generation → approval (for SQL). The RAG pipeline is a self-contained Python service layer with pluggable features. An Upstash Redis cache sits across all LLM calls. A Streamlit UI provides a developer-facing test harness with a built-in evaluation dashboard.

### Strengths

- **Rich feature set:** Hybrid search (dense + sparse + RRF), HyDE, cross-encoder reranking, CRAG with web fallback, Self-RAG reflection loop, and Text2SQL all work together cleanly.
- **Security depth:** Nine identifiable security layers including JWT auth, rate limiting, token budgets, llm-guard input/output scanning, PII redaction, prompt injection detection at both model-validator and middleware levels, and spotlighting.
- **Multi-tier caching:** Embeddings (7 days), RAG answers (1 hour), SQL generation (24 hours), SQL results (15 min), and intent classification (24 hours) are all independently cached with a graceful in-memory fallback.
- **Human-in-the-loop SQL:** LangGraph `interrupt()` suspends execution waiting for a human to approve generated SQL before execution — a rare and valuable safety feature.
- **Evaluation harness:** 40 golden questions with RAGAS metrics, feature-tagged profiles, forbidden-keyword post-checks, and source-overlap scoring exist for systematic quality tracking.
- **Good dependency hygiene:** `uv` + `pyproject.toml`, Python 3.12, Pydantic v2, ruff, mypy are all modern choices.

### Weaknesses

- **LangGraph graph is partially redundant with RAG service:** `run_rag()` in `rag_service.py` independently classifies intent, runs retrieval, and generates answers — the same logic the LangGraph graph also performs. This creates two parallel execution paths for RAG that diverge and can get out of sync.
- **No `local_storage.py` implementation:** `local_storage.py` is a 1-line empty file. The `DocCacheService` that depends on it will fail at runtime unless `storage_backend = "s3"`.
- **`SparseVectorIndex` is rebuilt on every query:** `_build_sparse_index()` scrolls all 10,000 Qdrant points on every sparse or hybrid search call, with no caching.
- **Redis clear is a no-op:** `query_cache.clear()` does nothing to Redis (Upstash SDK limitation acknowledged in comment). Cache clear endpoint is functionally broken for the Redis tier.
- **psycopg/psycopg2 mixing:** `graph.py` imports `psycopg` (v3) for the LangGraph checkpointer; `auth.py`, `admin.py`, `sql_service.py` all use `psycopg2` (v2). Both are installed with subtle API differences.
- **System prompt asks for JSON output but `generate()` doesn't enforce it:** The hardened system prompt mandates a JSON response but uses the plain `generate()` function (not `generate_with_json()`). Output structure depends entirely on model compliance.
- **Streamlit has hardcoded credentials:** Default username/password shown in the UI is `agent@demo.local`/`demo1234`, which is also seeded into the database.
- **No tests directory:** `pyproject.toml` declares `testpaths = ["tests"]` but no `tests/` directory exists.

### Scores

| Dimension | Score | Notes |
|---|---|---|
| Complexity | 8/10 | Advanced AI pipeline with multiple interacting subsystems |
| Maintainability | 5/10 | Dual execution paths, missing local storage, psycopg version mixing |
| Production Readiness | 5/10 | Core features work; critical bugs in storage layer, no tests, broken cache clear |

---

## 2. Folder Structure Analysis

```
enterprise-level-rag/
├── app/                         # Main application package
│   ├── api/                     # FastAPI routers
│   │   ├── admin.py             # Health check + cache management [ESSENTIAL]
│   │   ├── auth.py              # Register/Login endpoints [ESSENTIAL]
│   │   ├── query.py             # Primary /query and /query/sql/execute [ESSENTIAL]
│   │   └── __init__.py
│   ├── core/
│   │   ├── graph.py             # LangGraph state machine definition [ESSENTIAL]
│   │   └── state.py             # GraphState TypedDict [ESSENTIAL]
│   ├── middleware/
│   │   ├── auth.py              # JWT creation/verification, User model [ESSENTIAL]
│   │   └── rate_limiter.py      # Redis sliding-window rate limiter [ESSENTIAL]
│   ├── security/
│   │   ├── content_moderation.py  # PII redaction + output moderation [ESSENTIAL]
│   │   ├── input_guard.py         # llm-guard prompt injection scanning [ESSENTIAL]
│   │   ├── input_restructuring.py # Token count + truncate/summarize [ESSENTIAL]
│   │   ├── output_validator.py    # JSON output retry validator [OPTIONAL - not wired to main flow]
│   │   ├── spotlighting.py        # XML tagging of retrieved context [ESSENTIAL]
│   │   ├── system_prompt.py       # Hardened system prompt [ESSENTIAL]
│   │   └── token_budget.py        # Per-user daily token budget in Redis [ESSENTIAL]
│   ├── services/
│   │   ├── crag.py              # CRAG evaluation + web fallback [ESSENTIAL]
│   │   ├── doc_cache_service.py # Document deduplication cache [ESSENTIAL - but broken locally]
│   │   ├── document_processor.py # Docling PDF/DOCX/HTML chunker [ESSENTIAL]
│   │   ├── embedding_service.py  # OpenAI embeddings + cache [ESSENTIAL]
│   │   ├── hyde.py              # HyDE retriever [ESSENTIAL]
│   │   ├── llm_service.py       # OpenAI generate/generate_with_json [ESSENTIAL]
│   │   ├── query_cache_service.py # 5-tier Redis+memory cache [ESSENTIAL]
│   │   ├── rag_service.py       # Full RAG pipeline orchestrator [ESSENTIAL]
│   │   ├── reranking.py         # Cross-encoder + Voyage reranker [ESSENTIAL]
│   │   ├── router_service.py    # LLM intent classifier [ESSENTIAL]
│   │   ├── self_reflective.py   # Self-RAG reflection loop [ESSENTIAL]
│   │   ├── sparse_vector_service.py # TF-IDF + RRF fusion [ESSENTIAL]
│   │   ├── sql_service.py       # Text2SQL generation + execution [ESSENTIAL]
│   │   ├── vector_store.py      # Qdrant dense/sparse/hybrid search [ESSENTIAL]
│   │   └── web_search.py        # Tavily CRAG fallback [ESSENTIAL]
│   ├── storage/
│   │   ├── storage_backend.py   # Abstract StorageBackend + factory [ESSENTIAL]
│   │   ├── local_storage.py     # Local filesystem storage [BROKEN - 1 line, empty]
│   │   └── s3_storage.py        # S3 storage backend [ESSENTIAL]
│   ├── config.py                # Pydantic Settings [ESSENTIAL]
│   ├── main.py                  # FastAPI app factory [ESSENTIAL]
│   └── models.py                # Pydantic request/response models [ESSENTIAL]
├── eval/
│   ├── invokers.py              # ServiceInvoker for eval pipeline [ESSENTIAL]
│   ├── post_checks.py           # Forbidden keyword + source overlap checks [ESSENTIAL]
│   ├── profiles.py              # Eval flag profiles (naive→all) [ESSENTIAL]
│   ├── ragas_adapter.py         # RAGAS metric computation [ESSENTIAL]
│   ├── reporting.py             # Aggregate + table reporting [ESSENTIAL]
│   ├── run_ragas.py             # CLI eval harness [ESSENTIAL]
│   ├── schema.py                # Golden question schema loader [ESSENTIAL]
│   └── seed_questions.yaml      # 40 golden Q&A questions [ESSENTIAL]
├── notebooks/
│   ├── crag.ipynb               # CRAG prototype notebook [OPTIONAL]
│   ├── hybrid_search.ipynb      # Hybrid search experiments [OPTIONAL]
│   ├── reranker.ipynb           # Reranker comparison [OPTIONAL]
│   ├── srag.ipynb               # Self-RAG prototype [OPTIONAL]
│   └── text2sql.ipynb           # Text2SQL exploration [OPTIONAL]
├── scripts/
│   ├── seed_db.py               # Migration runner + doc ingestion [ESSENTIAL]
│   ├── serve.py                 # Uvicorn server launcher [ESSENTIAL]
│   └── streamlit_app.py         # Developer UI (1337 lines) [ESSENTIAL]
├── seed/
│   ├── docs/
│   │   ├── true_data/           # 50+ Kubernetes documentation files [ESSENTIAL]
│   │   └── noisy_data/          # Empty - populated by make seed-data [OPTIONAL]
│   └── migrations/
│       ├── 001_create_users.sql # Users table [ESSENTIAL]
│       └── 003_seed_k8s_ops.sql # K8s operational data schema + seed [ESSENTIAL]
├── .env.example                 # Environment variable reference [ESSENTIAL]
├── docker-compose.yml           # Postgres + Qdrant + App [ESSENTIAL]
├── Dockerfile                   # Python 3.12 slim image [ESSENTIAL]
├── Makefile                     # Developer workflow commands [ESSENTIAL]
├── PROJECT_REPORT.md            # Existing project documentation [OPTIONAL]
├── pyproject.toml               # Package config + deps [ESSENTIAL]
└── uv.lock                      # Locked dependency versions [ESSENTIAL]
```

**Missing files referenced by code:**
- `tests/` directory (referenced in `pyproject.toml`)
- `seed/migrations/002_seed_ecommerce.sql` (referenced in `003_seed_k8s_ops.sql` comment)
- `scripts/data_pipeline/` directory (referenced in `Makefile`)

---

## 3. Architecture Analysis

### FastAPI Architecture

Three routers mounted flat on the root application with no API versioning prefix:
- `POST /auth/register`, `POST /auth/login` — unprotected
- `POST /query`, `POST /query/sql/execute` — JWT-protected
- `GET /admin/health` — public; `GET/POST /admin/cache/*` — admin-JWT-protected

The `main.py` is deliberately minimal (9 lines). All logic lives in router files, services, and middleware. There is no lifespan event handler (FastAPI's `startup`/`shutdown` hooks), so the LangGraph graph is constructed at module import time via `graph = build_graph()` at the bottom of `graph.py`. This means the Postgres connection for LangGraph checkpointing is established on first import.

There is **no upload endpoint wired into the FastAPI app** despite the Streamlit UI calling `/documents/upload`. This endpoint exists in neither `admin.py` nor `query.py`. The Streamlit UI's upload tab will always return 404.

### LangGraph Workflow

```
START
  └─→ route_intent
       ├─→ "rag"    → generate_answer → finalize → END
       ├─→ "sql"    → generate_sql_node → request_sql_approval (interrupt) → execute_sql → generate_answer → finalize → END
       └─→ "hybrid" → retrieve_rag → generate_sql_node → request_sql_approval → execute_sql → generate_answer → finalize → END
```

The graph uses `PostgresSaver` for checkpointing, enabling the human-in-the-loop `interrupt()` pattern for SQL approval. Each query gets a fresh `thread_id` UUID. The state is defined in `GraphState` as a `TypedDict` with full field coverage for all paths.

### RAG Pipeline

The `run_rag()` function in `rag_service.py` is the single entry point for all RAG/SQL/Hybrid work when called from the LangGraph `generate_answer` node. Internally it:
1. Checks the RAG answer cache
2. Classifies intent (with its own cache)
3. Dispatches to `_retrieve()` → `_generate()` (for rag), `_run_sql_inline()` (for sql), or `_run_hybrid_inline()` (for hybrid)

**Important architectural issue:** `generate_answer` in `graph.py` calls `run_rag()` directly for the "rag" and "hybrid" intents, **bypassing the graph's earlier routing nodes for those intents**. The graph-level `retrieve_rag` node is only reached for the "hybrid" intent at the graph level, but then `run_rag` reruns retrieval inside itself. This creates double-retrieval for the hybrid path.

### Hybrid Search

1. Dense search: embed query → Qdrant cosine similarity  
2. Sparse search: build TF-IDF index from **all Qdrant points** → cosine similarity  
3. RRF fusion: combine ranked lists via `1/(k+rank)` scoring, `k=60` default

**Critical performance issue:** `_build_sparse_index()` scrolls up to 10,000 Qdrant points on every single sparse or hybrid search request. The TF-IDF index is never cached between requests.

### HyDE (Hypothetical Document Embeddings)

Generates N hypothetical answers (`hyde_num_hypotheses=3`) to the user's question using the answer LLM at temperature 0.7, then embeds all hypotheses + the original question and runs dense search for each. Results are deduplicated by text and merged by best score. This is the most expensive retrieval mode: 3 LLM calls + 4 embedding calls + 4 Qdrant queries per request.

### ReRanking

Two backends:
- **Local:** `sentence-transformers` CrossEncoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`) — loads model into memory on first use, no per-instance caching (model reloads if `Reranker()` is instantiated multiple times)
- **Voyage:** `voyageai` SDK with `rerank-2.5` model — API-based

The reranker fetches `reranker_initial_top_k=20` candidates first, then reranks down to `top_k`. The local model is instantiated fresh on every call (`Reranker()` is created inside `_retrieve()` with no singleton caching).

### CRAG (Corrective RAG)

1. Grade retrieved chunks using `llm_model_grader` → `CRAGEvaluation` (relevance score 0–1)  
2. If `relevance_score < crag_relevance_threshold (0.7)`: fall back to Tavily web search  
3. Return either original chunks or web results

CRAG adds one LLM grading call per query regardless of whether web fallback is triggered. This is always enabled by default (`crag_enabled_by_default=True`).

### Self-RAG

A reflection loop after initial answer generation:
1. Generate answer
2. Score it on 4 criteria (relevance, accuracy, completeness, clarity) via LLM
3. If `needs_regeneration=True` and `score < 0.85` and `iterations < 2`: refine question and retry
4. Maximum 2 retries (configurable)

Disabled by default (`self_reflective_enabled_by_default=False`). When enabled, this can add up to 3 LLM calls (initial + 2 retries) plus 3 reflection scoring calls.

### Text2SQL

Does **not** use Vanna (despite `vanna` being listed as a dependency and configured in settings). Instead uses a hand-rolled schema introspection approach:
1. `_build_schema_context()` queries `information_schema.columns` from Postgres
2. Formats schema as plain text
3. Sends schema + question to GPT-4o with a prompt asking for JSON `{sql, explanation}`
4. Parses response, validates with `is_select_only()`, executes

SQL generation is cached by question (24h TTL). SQL results are cached by SQL text (15min TTL).

`is_select_only()` checks for dangerous keywords but uses a simple regex that could be bypassed with SQL comments or case variations not covered by the current patterns.

### Caching

The `QueryCacheService` is a two-tier system:
- **L1 (Redis):** Upstash Redis via HTTP API. Primary store for all tiers.
- **L2 (Memory):** Python dict with manual TTL expiry. Fallback when Redis is unavailable.

Five independent cache namespaces with SHA-256 keying:
| Tier | TTL | Key basis |
|---|---|---|
| intent | 24h | question text (lowercased) |
| rag_answer | 1h | question + flags dict |
| sql_gen | 24h | question text |
| sql_result | 15min | normalized SQL text |
| embedding | 7d | raw text |

Cache keys use full SHA-256 hashes. The embedding cache is shared with `embed_texts()` which checks cache before API calls.

### Guardrails

Layer order in the `/query` endpoint (numbered as they appear in the code):
1. JWT authentication (middleware)
2. Pydantic field validation on `QueryRequest` (regex injection patterns in `field_validator`)
3. Sliding-window rate limit (Redis, per user)
4. Daily token budget check (Redis, per user)
5. Input restructuring / truncation (tiktoken)
6. llm-guard input scan (PromptInjection + Toxicity + BanTopics + TokenLimit)
7. Content moderation + PII redaction (input)
8. Spotlighting (retrieved context wrapped in XML with security preamble)
9. Hardened system prompt (behavioral rules + format enforcement)
10. Content moderation + PII redaction (output)

### Storage

Two storage backends behind an abstract `StorageBackend` interface:
- **LocalStorage:** Empty file — not implemented
- **S3Storage:** Full boto3 implementation

`DocCacheService` uses this for document deduplication (content-hash → metadata.json). It is invoked from the admin upload endpoint (which doesn't exist in the API).

---

## 4. Request Flow

### Complete Request Lifecycle

```
User sends: POST /query
  {question, top_k, search_mode, enable_rerank, enable_hyde, enable_crag, enable_self_reflective}

├── [FastAPI] HTTPBearer extracts JWT from Authorization header
│     → get_current_user() decodes JWT → User{username, is_admin}
│     [FAIL: 401 Unauthorized]
│
├── [rate_limiter.py] is_allowed_user()
│     → Redis ZREMRANGEBYSCORE + ZADD + ZCARD sliding window
│     [FAIL: 429 Rate Limit Exceeded]
│
├── [token_budget.py] check_budget()
│     → Redis GET token_budget:{user}:{date}
│     → compare estimated tokens (count_tokens + reserved_output_tokens)
│     [FAIL: 429 Token Budget Exceeded]
│
├── [input_restructuring.py] restructure_input()
│     → tiktoken count; if >2000: truncate or summarize to 2000
│     [PASS: restructured text]
│
├── [input_guard.py] check_input_safe()
│     → llm-guard: PromptInjection + Toxicity + BanTopics + TokenLimit
│     [FAIL: 400 injection_blocked]
│
├── [content_moderation.py] moderate_and_redact() — INPUT
│     → llm-guard: Sensitive (PII redaction) + Toxicity + BanTopics
│     [FAIL: 400 content_blocked] OR [PASS: redacted_text]
│
├── [graph.py] graph.invoke(question, user_id, flags, thread_id)
│   │
│   ├── [route_intent] → classify_intent()
│   │     → check Redis intent cache
│   │     → if miss: GPT-4o-mini JSON classification (sql/rag/hybrid)
│   │     → cache result
│   │
│   ├── IF intent == "rag":
│   │     → generate_answer() → run_rag() → _retrieve() + _generate()
│   │
│   ├── IF intent == "sql":
│   │     → generate_sql_node() → sql_service.generate_sql()
│   │       → check SQL gen cache → schema introspection → GPT-4o
│   │     → request_sql_approval() → interrupt() ← STOPS HERE
│   │       API returns pending_sql block to client
│   │     [Client calls POST /query/sql/execute with approved=true/false]
│   │     → execute_sql() → sql_service.execute_sql()
│   │       → SELECT-only validation → Postgres query → cache result
│   │     → generate_answer() → format rows as JSON
│   │
│   └── IF intent == "hybrid":
│         → retrieve_rag() → run_rag() [embed + hybrid_search + CRAG]
│         → generate_sql_node() → request_sql_approval() [interrupt]
│         → execute_sql()
│         → generate_answer() → _generate_hybrid_answer()
│           synthesizes SQL rows + RAG context
│
├── [content_moderation.py] moderate_and_redact() — OUTPUT
│     → PII redaction on answer text
│     [FAIL: 500 output_blocked]
│
├── [token_budget.py] consume_budget()
│     → Redis INCRBY token_budget:{user}:{date}
│
└── RETURN ChatResponse{answer, sources, confidence, cache_hit, metadata}
```

---

## 5. Dependency Analysis

| Package | Version | Purpose | Status |
|---|---|---|---|
| fastapi | ≥0.115.0 | Web framework | **Required** |
| uvicorn[standard] | ≥0.32.0 | ASGI server | **Required** |
| python-multipart | ≥0.0.12 | Form/file upload parsing | **Required** (needed for upload endpoint once built) |
| pydantic | ≥2.9.0 | Data validation | **Required** |
| pydantic-settings | ≥2.6.0 | Settings from env | **Required** |
| openai | ≥1.54.0 | LLM + embeddings | **Required** |
| tiktoken | ≥0.8.0 | Token counting | **Required** |
| qdrant-client | ≥1.12.0 | Vector DB client | **Required** |
| docling | ≥2.9.0 | PDF/DOCX/HTML parsing | **Required** |
| vanna[openai,postgres] | ≥0.7.0 | Text2SQL framework | **Unused** — replaced by custom SQL service |
| psycopg2-binary | ≥2.9.10 | Postgres driver (v2) | **Required** (used in auth, admin, sql_service) |
| upstash-redis | ≥1.2.0 | Redis client | **Required** |
| pyjwt | ≥2.10.0 | JWT creation/verification | **Required** |
| passlib[bcrypt] | ≥1.7.4 | Password hashing | **Required** (bcrypt used directly) |
| loguru | ≥0.7.2 | Structured logging | **Required** |
| langgraph | ≥0.2.50 | State machine orchestration | **Required** |
| langgraph-checkpoint-postgres | ≥2.0 | LangGraph PostgreSQL checkpointer | **Required** |
| sentence-transformers | ≥3.3.0 | Local cross-encoder reranker | **Optional** (required if reranker_backend=local) |
| voyageai | ≥0.3.0 | Voyage reranking API | **Optional** (required if reranker_backend=voyage) |
| tavily-python | ≥0.5.0 | Web search for CRAG fallback | **Optional** (required if CRAG triggers web search) |
| llm-guard | ≥0.3.15 | Input/output security scanning | **Required** (but gracefully degrades if absent) |
| boto3 | ≥1.35.0 | AWS S3 storage backend | **Optional** (required if storage_backend=s3) |
| pypdf | ≥5.1.0 | PDF processing | **Replaceable** (docling handles PDFs; pypdf may be redundant) |
| pyyaml | ≥6.0 | YAML parsing (eval seed questions) | **Required** |
| faker | ≥33.0.0 | Synthetic K8s ops data generation | **Optional** (only for data pipeline scripts) |
| psycopg[binary] | installed separately in Dockerfile | psycopg v3 for LangGraph checkpointer | **Required** — not in pyproject.toml! |
| scikit-learn | transitive dep of sentence-transformers | TF-IDF vectorizer for sparse index | **Required** |

**Dev-only:**
| Package | Purpose | Status |
|---|---|---|
| pytest, pytest-asyncio | Testing | Required for tests (no tests exist yet) |
| httpx | Async HTTP client for tests | Required |
| ruff | Linter + formatter | Required |
| mypy | Type checker | Optional |
| ragas | RAG evaluation metrics | Required for eval |
| reportlab | PDF generation for data pipeline | Optional |
| python-docx | DOCX generation for data pipeline | Optional |
| streamlit | Developer UI | Required |

**Key issue:** `psycopg[binary]` (v3) is installed manually in the Dockerfile (`RUN uv pip install --system --no-cache 'psycopg[binary]'`) but is **not** listed in `pyproject.toml`. Anyone installing from `pyproject.toml` alone will fail when the LangGraph graph tries to import.

---

## 6. Configuration Review

### Environment Variables (`.env.example`)

Well-organized and documented with inline comments. All settings map to `Settings` class in `config.py`. No duplicates.

**Issues:**
- `LOG_JSON=false` — comment says `true in prod` but there is no enforcement or startup check
- `JWT_SECRET=change-me-to-a-long-random-string` — placeholder with no validation that this was changed
- `VANNA_MODEL`, `VANNA_TEMPERATURE`, `VANNA_SEED` — Vanna is not used; these settings are dead config
- `S3_CACHE_BUCKET` and `AWS_REGION` have no effect when `storage_backend=local`

### Settings Class (`config.py`)

Uses `pydantic-settings` `BaseSettings` with `.env` file loading. All values have defaults, allowing the app to start without a `.env` file (with broken functionality for many features).

**Trailing whitespace / blank lines at the bottom (lines 82–89)** — minor code quality issue.

### Docker (`Dockerfile`)

- Uses `python:3.12-slim` — appropriate
- Installs `libgl1` and `libglib2.0-0` for Docling's OpenCV dependency
- Separate `RUN` for torch (large layer, CPU-only wheels) — good caching strategy
- `psycopg[binary]` installed separately from main deps — creates invisible dependency
- `MPS` (Apple Silicon) accelerator configured in `document_processor.py` — will silently fall back to CPU in a Linux container but is wasteful config

### `docker-compose.yml`

- No Redis service — relies on external Upstash. For fully local development this means Redis must be configured externally
- Qdrant v1.17.0 pinned — good
- Postgres 16 — appropriate
- `./app:/app/app` volume mount means code changes are live-reloaded in the container, but `scripts/serve.py` starts without `--reload`, so changes don't hot-reload
- `UPSTASH_REDIS_URL` and `UPSTASH_REDIS_TOKEN` are passed through from host environment with no default — app will start but Redis cache silently falls back to in-memory

### Makefile

Clean, well-organized. Commands:
- `make install` / `make sync` — dependency management
- `make seed` — runs `seed_db.py` (migrations + user seeding + doc ingestion)
- `make api` / `make streamlit` — development server launchers
- `make eval-*` — all evaluation profiles
- `make test` / `make lint` / `make format` — standard dev workflow

**Issues:**
- `make seed-data` calls `bash scripts/data_pipeline/run_all.sh` which does not exist in the repository
- `make eval-diff` relies on a `eval.diff` module that is not in the repository
- `eval-legacy` is a stub pointing to `eval-baseline`

### `pyproject.toml`

Well-structured. Uses `hatchling` build backend. Ruff and mypy configured appropriately.

**Issues:**
- `testpaths = ["tests"]` but no `tests/` directory exists
- Comment `# === Phase 2+ deps pinned now to avoid churn ===` reveals incremental development phases — these phase markers are no longer meaningful

---

## 7. API Review

### `POST /auth/register`

- **Purpose:** Create a new user account and return a JWT token
- **Input:** `{username: str, password: str}` — untyped `dict` body (no Pydantic model)
- **Output:** `{token: str}`
- **Authentication:** None (public)
- **Dependencies:** Postgres (direct psycopg2), Redis (rate limiting by IP)
- **Issues:** Body is `dict` not a typed Pydantic model — no validation of password strength or username format. Passwords could be empty strings.

### `POST /auth/login`

- **Purpose:** Authenticate and return a JWT token
- **Input:** `{username: str, password: str}` — untyped `dict` body
- **Output:** `{token: str}`
- **Authentication:** None (public)
- **Dependencies:** Postgres, Redis (rate limiting by IP)
- **Issues:** Same untyped body issue. No account lockout after failed attempts (only rate limit by IP).

### `POST /query`

- **Purpose:** Main AI query endpoint — routes to RAG, SQL, or Hybrid pipeline
- **Input:** `QueryRequest{question, top_k, search_mode, enable_rerank, enable_hyde, enable_crag, enable_self_reflective}`
- **Output:** `ChatResponse{answer, sources, confidence, pending_sql, cache_hit, cost_saved, metadata}`
- **Authentication:** JWT required
- **Dependencies:** LangGraph graph → Qdrant, Postgres, OpenAI, Redis, Tavily (optional), llm-guard
- **Issues:** `cost_saved` is always `"$0.00"` — hardcoded, never computed. `confidence` is hardcoded to 0.7 for RAG, 0.9 for SQL, 0.8 for hybrid — not meaningful.

### `POST /query/sql/execute`

- **Purpose:** Resume a suspended LangGraph thread after SQL approval/rejection
- **Input:** `{query_id: str, approved: bool}`
- **Output:** `ChatResponse`
- **Authentication:** JWT required
- **Dependencies:** LangGraph graph with PostgreSQL checkpointer
- **Issues:** No validation that `query_id` belongs to the requesting user. Any authenticated user can approve another user's SQL query.

### `GET /admin/health`

- **Purpose:** Parallel health check of all external services
- **Input:** None
- **Output:** `{status, qdrant, postgres, redis, openai, tavily}` (all booleans)
- **Authentication:** None (public) — any unauthenticated caller can see service topology
- **Issues:** Exposes infrastructure information without authentication. Tavily health check actually calls `search_web("health check")` consuming API quota.

### `GET /admin/cache/stats`

- **Purpose:** Return cache hit/miss/set counts per tier
- **Input:** None
- **Output:** Cache statistics per tier
- **Authentication:** Admin JWT required
- **Issues:** Stats are in-process memory only — not meaningful in a multi-process or multi-replica deployment.

### `POST /admin/cache/clear`

- **Purpose:** Clear all cache tiers
- **Input:** None
- **Output:** `{status, cleared: list[str]}`
- **Authentication:** Admin JWT required
- **Issues:** Redis clear is a no-op (documented in code with a `pass` statement). Only in-memory cache is actually cleared.

### Missing Endpoints

- **`POST /documents/upload`** — Called by Streamlit UI but does not exist. Would use Docling + `doc_cache_service` + embedding + Qdrant upsert.
- **`GET /health`** (unauthenticated, lightweight) — no simple `/health` for load balancer probes

---

## 8. LangGraph Analysis

### State (`GraphState`)

A `TypedDict` with 22 fields spanning all possible paths:
- Core: `question`, `user_id`, `flags`
- Routing: `intent`
- SQL path: `generated_sql`, `sql_explanation`, `sql_approved`, `sql_rows`, `sql_cache_hit`
- RAG path: `hypotheses`, `retrieved_chunks` (additive via `Annotated[list, add]`), `reranked_chunks`, `spotlighted_context`, `crag_evaluation`, `web_results`, `rag_cache_hit`
- Reflection: `raw_answer`, `reflection`, `reflection_iterations`, `refined_question`
- Output: `final_answer`, `sources`, `confidence`, `chunk_previews`
- Telemetry: `cache_hits`, `cost_saved_usd`

**Issue:** Many state fields (`hypotheses`, `reranked_chunks`, `crag_evaluation`, `web_results`, `raw_answer`, `reflection`, `cost_saved_usd`) are populated by `rag_service.py` internally but never written back to the graph state. They are effectively dead fields in the graph.

### Nodes

| Node | Function | Notes |
|---|---|---|
| `route_intent` | `classify_intent()` → sets `intent` | Uses LLM cache |
| `retrieve_rag` | `run_rag()` for context gathering | Only reached for "hybrid"; confusingly calls full run_rag |
| `generate_sql_node` | `sql_service.generate_sql()` | Reached for "sql" and "hybrid" paths |
| `request_sql_approval` | `interrupt()` | Suspends graph, returns `pending_sql` to caller |
| `execute_sql` | `sql_service.execute_sql()` | Only runs if `sql_approved=True` |
| `generate_answer` | Main answer synthesis | Calls `run_rag()` again for "rag" intent |
| `finalize` | No-op return `{}` | Exists only to provide a clean terminal node |

### Edges

```
START → route_intent
route_intent → [sql: generate_sql_node | rag: generate_answer | hybrid: retrieve_rag]
retrieve_rag → generate_sql_node          # hybrid path: RAG then SQL
generate_sql_node → request_sql_approval  # always requires human approval
request_sql_approval → execute_sql
execute_sql → generate_answer
generate_answer → finalize
finalize → END
```

### Routing Logic

`classify_intent()` in `router_service.py` uses two mechanisms:
1. **Keyword shortcut:** if question contains document-domain hints (`elastic-cache`, `fast-dllm`, `llada`, `gsm8k`, etc.) → forced `"rag"`. These keywords appear to be from a previous/different domain, not Kubernetes — they look like research paper terms.
2. **LLM classification:** GPT-4o-mini with a JSON-mode system prompt → `{intent: "sql"|"rag"|"hybrid"}`

### Checkpoints and Interrupts

`PostgresSaver` stores all graph state snapshots in Postgres. Each query gets a new `thread_id` UUID. The `interrupt()` in `request_sql_approval` suspends execution and returns control to the caller. Resuming requires the same `thread_id` passed to `Command(resume=...)`.

**Issue:** `_get_checkpointer()` creates a new `psycopg.connect()` (synchronous, persistent connection) every time `build_graph()` is called. `build_graph()` is called once at module import, so the connection is shared for the lifetime of the process. No connection pooling.

### Retry Logic

No automatic retry in the graph itself. The Self-RAG reflection loop (up to 2 retries) lives entirely within `rag_service.py`, invisible to the graph state machine.

### Failure Handling

Nodes have minimal error handling:
- `execute_sql` catches exceptions and sets `final_answer` to an error message
- `generate_answer` handles missing `sql_rows` gracefully
- No circuit breaker, no retry logic at the graph level
- If `generate_sql_node` raises (e.g. OpenAI failure), the exception propagates uncaught to the API endpoint

---

## 9. AI Pipeline Review

### HyDE (Hypothetical Document Embeddings)

**How it works:** Generate 3 hypothetical answers at temperature 0.7, embed each + the original question, run dense search for all 4, deduplicate by text, sort by score.

**Contribution:** Bridges vocabulary gaps where the user's phrasing doesn't match document terminology. Most effective for layman queries ("How do I make my app keep running if a server dies?" → retrieves Deployment/replica docs).

**Cost:** 3 LLM calls + 4 embeddings + 4 Qdrant queries per request. Most expensive retrieval mode.

### Hybrid Search

**How it works:** Dense (Qdrant cosine) + Sparse (TF-IDF cosine) → RRF fusion.

**Contribution:** Covers both semantic similarity (dense) and exact token matching (sparse). Critical for technical identifiers like `ErrImagePull`, `OOMKilled`, `imagePullPolicy`.

**Problem:** Sparse index rebuilt from scratch on every call. For 10,000 documents, this is a full Qdrant scroll + sklearn TF-IDF fit on every hybrid/sparse query. Latency impact: significant.

### BM25 / Sparse Search

Uses TF-IDF (not BM25) via scikit-learn `TfidfVectorizer`. BM25 is mentioned in the Streamlit UI comments but the implementation is TF-IDF cosine similarity. TF-IDF and BM25 produce similar rankings in practice but differ in term frequency saturation.

### RRF (Reciprocal Rank Fusion)

Standard RRF implementation with `k=60`. Uses chunk text as the fusion key. This means identical text chunks from different sources get merged, losing source diversity. Should use a content-hash or stable chunk ID instead.

### Cross-Encoder Reranking

**Local:** CrossEncoder scores `(query, chunk)` pairs with a sentence-transformer model. Loads model on first use — cold start adds ~2–5 seconds.

**Voyage:** API-based reranking, lower latency after network overhead.

**Problem:** `Reranker()` is instantiated fresh in `_retrieve()` on every call. The local CrossEncoder model (`_local_model`) is an instance variable that gets garbage collected between calls, triggering model reload.

### CRAG (Corrective RAG)

**How it works:** One LLM grading call on every RAG query (when enabled). If score < 0.7, fall back to Tavily.

**Contribution:** Handles out-of-distribution queries gracefully, prevents confident hallucination on topics not in the corpus.

**Cost:** 1 extra LLM call per query always (enabled by default). If CRAG fires web search, adds 1 Tavily API call.

**Edge case:** When `chunks=[]` (no retrieval results), CRAG immediately triggers web search without grading. This is correct behavior but means Tavily is always called for empty results.

### Self-RAG

**How it works:** After initial answer generation, score the answer on 4 criteria (relevance, accuracy, completeness, clarity) via LLM. If weak, refine the question and regenerate. Up to 2 retries.

**Contribution:** Significantly improves answers to vague queries ("explain", "what is wrong", "tell me about pods"). The refinement prompt is detailed and well-engineered.

**Cost (worst case):** 3 generation LLM calls + 3 reflection scoring calls per query. Disabled by default.

### Text2SQL

**How it works:** Schema introspected from `information_schema.columns`, formatted as plain text, sent to GPT-4o with generation temperature=0. Response parsed as JSON `{sql, explanation}`, validated by `is_select_only()`, executed via psycopg2.

**Contribution:** Enables natural-language queries over structured operational data (incidents, clusters, pods, etc.).

**Limitations:** No Vanna training data, no few-shot examples — the model only has the schema to work from. Complex JOINs or analytical queries may fail silently. The `is_select_only()` guard is necessary but incomplete (e.g., CTEs with `INSERT` in a `WITH ... INSERT INTO` could bypass it).

### Caching

Five-tier cache with graceful degradation. Cache keys are deterministic SHA-256 hashes. The RAG answer cache key includes `flags` (search mode, toggles, top_k) so different feature configurations get different cache entries. This is correct behavior but reduces effective hit rate.

### Evaluation (RAGAS)

Uses RAGAS metrics: faithfulness, context precision, context recall, answer relevancy. The `run_ragas.py` harness supports 40 golden questions across 8 feature categories. Profiles allow comparing naive vs. each enhancement.

**Missing:** No CI integration — evaluation must be run manually.

---

## 10. Security Review

### Layer 1: Pydantic Validation (`models.py`)

`ChatRequest` and `QueryRequest` both have `field_validator` applying regex injection patterns. Four patterns catch common injection attempts. This fires before any other processing.

**Gap:** The patterns are simple string matches. Sophisticated injections using Unicode lookalikes, HTML entities, or multi-step jailbreaks won't be caught.

### Layer 2: JWT Authentication (`middleware/auth.py`)

- HS256 JWT with configurable expiry (default 60 min)
- `bcrypt` with rounds=12 for password hashing
- `is_admin` claim embedded in JWT payload
- No refresh token mechanism — expired tokens require re-login

**Gap:** JWT secret defaults to placeholder value — no startup validation that `jwt_secret` has been changed. An empty `jwt_secret` would still work cryptographically but be trivially guessable.

### Layer 3: Rate Limiting (`middleware/rate_limiter.py`)

Sliding-window rate limiting using Redis sorted sets. Two types:
- IP-based: for auth endpoints (register, login)
- User-based: for /query endpoint

`RateLimiter.is_allowed()` uses a Redis pipeline for atomicity. The window is correctly implemented.

**Gap:** Rate limiting requires Redis. If Redis is down (and only in-memory cache is active), rate limiting is completely bypassed — `get_redis_client()` in `rate_limiter.py` will raise on Redis operations. There is no graceful degradation.

### Layer 4: Token Budget (`security/token_budget.py`)

Per-user daily token budget tracked in Redis. Budget key expires at midnight UTC.

**Gap:** Same Redis dependency issue. If Redis is unavailable, `check_budget()` raises an exception rather than allowing/denying gracefully. Also uses the same global Redis client as rate limiting.

### Layer 5: Input Restructuring (`security/input_restructuring.py`)

Token-based truncation/summarization prevents oversized inputs. The `summarize_text()` is a greedy sentence selection — not actual LLM summarization, despite the function name.

### Layer 6: llm-guard Input Scan (`security/input_guard.py`)

Uses llm-guard's `PromptInjection`, `Toxicity`, `BanTopics`, `TokenLimit` scanners. Gracefully returns "safe" if llm-guard is unavailable.

**Gap:** `_scanners` is a module-level global. If the first call triggers an import error, `_scanners` stays `None` and all subsequent calls return safe (silent degradation).

### Layer 7: Content Moderation + PII Redaction (`security/content_moderation.py`)

Applied both to **input** (before sending to LLM) and **output** (before returning to user). PII redaction uses llm-guard's `Sensitive` scanner with regex fallback for email, phone, credit card, IP patterns.

**Gap:** The regex-based IP redaction will redact valid Kubernetes IP addresses in answers. An answer mentioning "the service is at 10.0.0.1" would have the IP redacted, reducing utility.

### Layer 8: Spotlighting (`security/spotlighting.py`)

Retrieved context is wrapped in XML tags with a security preamble labeling it as "UNTRUSTED DATA." This is an important defense against indirect prompt injection via malicious document content.

### Layer 9: Hardened System Prompt (`security/system_prompt.py`)

Comprehensive behavioral rules including domain restriction, no code execution, citation requirements, PII prohibition, and explicit role/behavior lock.

**Gap:** The system prompt asks the LLM to "Return a JSON object with exactly these fields" but the actual `generate()` call doesn't enforce `response_format={"type": "json_object"}`. The LLM may return prose instead of JSON, causing `output_validator.py`'s retry logic to be needed — but `output_validator.py` is not wired into the main RAG flow.

### Missing Protections

- No HTTPS enforcement (no TLS termination in the app — expected to be handled by a reverse proxy but not documented)
- No CSRF protection (API is stateless JWT, so not critical but worth noting)
- No request body size limit beyond token count
- SQL injection via generated SQL is mitigated by `is_select_only()` but not by parameterized queries (raw SQL string execution)
- No audit log of queries per user
- `/admin/health` is publicly accessible and reveals infrastructure topology

---

## 11. Performance Review

### Critical Bottlenecks

**1. Sparse index rebuild on every query (`vector_store.py:61-80`)**
`_build_sparse_index()` scrolls 10,000 Qdrant documents on every hybrid or sparse search. TF-IDF `fit_transform()` on 10,000 documents takes hundreds of milliseconds. This is the single largest avoidable performance issue. An in-process singleton with invalidation would fix this.

**2. `Reranker()` instantiated per-request (`rag_service.py:61`)**
`Reranker()` creates a new instance on every `_retrieve()` call. The `_local_model` is an instance variable, so the CrossEncoder model is not shared across requests. First request per-process loads the model (2–5 seconds cold start). Subsequent requests reload from disk on each call if the instance is garbage collected.

**3. Multiple `classify_intent()` calls per request**
`run_rag()` calls `classify_intent()` internally. When called from the LangGraph `generate_answer` node (for "rag" intent), the graph has already called `route_intent` which called `classify_intent`. This means intent classification runs twice per request for the "rag" path. The intent cache mitigates this but the Redis call still happens.

**4. HyDE: 3 LLM + 4 embedding + 4 Qdrant calls**
When HyDE is enabled: 3 × LLM call + 4 × `embed_texts()` + 4 × `search()`. Without caching, this easily takes 8–15 seconds per query.

**5. CRAG grading call always executes (when enabled)**
One extra LLM call per query when CRAG is enabled (the default). The grading uses `llm_model_grader` (gpt-4o-mini) which is faster but still adds 300–800ms.

**6. Self-RAG: up to 6 LLM calls**
When enabled with 2 retries: 3 generate + 3 reflect = 6 LLM calls. With CRAG also enabled, add 3 more grading calls = 9 LLM calls per request worst case.

**7. `_get_db_conn()` creates a new connection per request (`auth.py`, `admin.py`)**
Every login and register call creates a new psycopg2 connection, queries, then closes it. No connection pooling.

**8. `SQLService._build_schema_context()` queries Postgres on every new instance**
`SQLService` is instantiated in `rag_service.py:138` (`_run_sql_inline`) and `rag_service.py:181` (`_run_hybrid_inline`) on every SQL-intent query. `_schema_context` is cached as an instance variable — but since a new instance is created each time, the cache never hits. Schema is re-queried every time.

### Slow Functions Summary

| Function | Issue | Severity |
|---|---|---|
| `_build_sparse_index()` | 10k doc scroll + TF-IDF fit on every call | CRITICAL |
| `Reranker.__init__` + `CrossEncoder` load | Model reload per request | HIGH |
| `HyDERetriever.retrieve()` | 3+4 LLM+embed calls | HIGH |
| `SQLService._build_schema_context()` | DB query per SQL request | MEDIUM |
| `classify_intent()` — double call | Two Redis hits per rag query | LOW (cached) |
| `_get_db_conn()` | New Postgres connection per auth call | MEDIUM |

---

## 12. Code Quality Review

### Duplicated Code

- **Intent classification logic:** `classify_intent()` is called in `rag_service.py:run_rag()` AND the LangGraph `route_intent` node — both serve the same purpose but are separate calls
- **JSON serialization helper:** `_safe_json_default()` / `_safe_json_dumps()` exists in `graph.py` and a near-identical `_serialize_value()` / `_serialize_row()` exists in `sql_service.py`
- **Injection validation patterns:** Almost identical regex patterns in `models.py` (`ChatRequest`) and `models.py` (`QueryRequest`) — duplicated in two `field_validator` methods
- **`_run_sql_inline()` and `generate_sql_node` + `execute_sql`:** Both do SQL generation + execution. The graph nodes and the `rag_service` inline functions are parallel implementations of the same logic

### Large Files

- `scripts/streamlit_app.py` — 1,337 lines. Should be split into modules (auth_tab, query_tab, eval_tab, etc.)
- `app/services/rag_service.py` — 290 lines with multiple independent responsibilities (retrieval, generation, SQL, hybrid, trace variants)
- `eval/seed_questions.yaml` — 594 lines (acceptable for a data file)

### Large Functions

- `main()` in `streamlit_app.py` spans the entire Streamlit layout
- `_eval_dashboard_section()` is ~300 lines in one function

### Code Smells

- `finalize()` in `graph.py` returns `{}` and exists only as a terminal node — empty function with no purpose
- `run_rag_with_trace_no_cache = run_rag_with_trace` — alias that implies different behavior (no cache) but actually does the same thing
- `_looks_like_document_question()` in `router_service.py` has hardcoded hints from a different domain (`elastic-cache`, `fast-dllm`, `llada`, `gsm8k`, `gamma`, `humaneval`, `qkv`) — these appear to be remnants of a previous RAG project, not Kubernetes-related
- `bcrypt` is imported directly in `middleware/auth.py` but `passlib[bcrypt]` is the declared dependency — direct `import bcrypt` bypasses passlib's abstraction
- `type("Chunk", (), {"text": s, "source": s, "score": 0.0})()` in `graph.py:58` — dynamic class creation for duck-typing instead of using the `RetrievedChunk` model

### Inconsistent Naming

- `llm_model_answer` vs `llm_model_grader` — clear but asymmetric naming
- `enable_crag` vs `enable_self_reflective` — inconsistent prefix style
- `run_rag` vs `run_rag_with_trace` vs `run_rag_with_trace_no_cache` — proliferating function variants

### Dead Code

- `output_validator.py` (`validate_with_retry`) — never called in production code paths
- `services/__init__.py` — empty
- `storage/__init__.py` — empty
- `api/__init__.py` — empty
- `core/__init__.py` — empty
- `_document_hints` in `router_service.py` — contains irrelevant non-Kubernetes domain hints
- `ReflectionResult` fields in `GraphState` (`raw_answer`, `reflection`) — set internally in `rag_service.py` but never written to graph state
- `cost_saved_usd` in `GraphState` — never populated
- `sql_cache_hit` in `GraphState` — never populated
- `rag_cache_hit` in `GraphState` — never populated (commented out in `graph.py:63-64`)

### Circular Dependency Risk

`rag_service.py` imports from almost every other service module. The dependency graph is a star topology centered on `rag_service.py`. No circular imports currently but `router_service.py` importing from `query_cache_service` and `rag_service.py` also importing from both creates potential for circular import if refactored.

### Unused Imports

- `from app.services.router_service import classify_intent` in `rag_service.py` — imported and used, but also called from graph which re-imports separately
- `import json as _json` inside functions `_run_sql_inline` and `_run_hybrid_inline` — local import inside a function that could be at module level

---

## 13. Deployment Review

### Can It Deploy Today?

**Partially yes, with caveats:**

**Will work:**
- Basic RAG queries (dense search, LLM generation)
- Authentication
- Admin health check
- CRAG (if Tavily key configured)
- SQL generation/approval/execution

**Will NOT work:**
- Sparse or hybrid search → `local_storage.py` is empty but this doesn't block search itself; however `_build_sparse_index()` rebuilds from scratch every time
- Document upload via Streamlit UI → endpoint doesn't exist in FastAPI
- Cache clear → Redis tier is a no-op
- Any data pipeline (`make seed-data`) → scripts directory doesn't exist

**Blockers:**
- `psycopg[binary]` (v3) is not in `pyproject.toml` — installing only from `pyproject.toml` breaks LangGraph checkpointer
- `local_storage.py` is empty — `DocCacheService` will fail if initialized with local backend (but currently only called from the missing upload endpoint)

### Docker

The `Dockerfile` builds a working image assuming all environment variables are provided. The multi-layer approach (torch first, then app) is good for cache efficiency. Approximately 2–3 GB image size due to torch + sentence-transformers.

### Render / Railway

Both platforms can run the Docker image. Key requirements:
- Postgres: can use managed Postgres (both Render and Railway offer this)
- Qdrant: **no managed Qdrant on either platform** — would need Qdrant Cloud or self-hosted
- Redis: Upstash Redis is already cloud-native (correct choice for serverless deployment)
- Environment: all secrets via env vars (already implemented)

**Railway-specific issue:** LangGraph PostgreSQL checkpointer requires `psycopg[binary]` which installs a native binary. The Dockerfile handles this but Railway's buildpack might not.

### Vercel Compatibility

**Not compatible.** Vercel runs serverless functions with 10-second execution limits. This application has:
- Long-running LLM calls (5–30 seconds)
- Persistent database connections (LangGraph checkpointer)
- Local model loading (CrossEncoder)
- In-process TF-IDF index

### Database (Postgres)

Schema is clean and well-organized:
- `users` table for auth
- K8s operational tables: `clusters`, `nodes`, `deployments`, `pods`, `incidents`, `alerts`, `oncall_logs`

No indexes defined beyond primary keys and unique constraints. At scale, queries over `incidents`, `pods`, and `alerts` tables will need indexes on `cluster_id`, `status`, `severity`, and timestamp columns.

### Redis (Upstash)

Using Upstash Redis over HTTP (not native Redis protocol). This is appropriate for serverless and cloud deployment but adds HTTP overhead per cache operation. The rate limiter's pipeline operations may have higher latency than native Redis pipelines.

### Qdrant

Using Qdrant v1.17.0. Collection has no named vectors (single default vector space). At scale, would benefit from payload indexes for filtered searches and quantization for memory efficiency. Currently limited to 10,000 document scroll for sparse index — this is a hard practical limit.

---

## 14. Frontend Review

### Streamlit Application (`scripts/streamlit_app.py`, 1,337 lines)

#### Strengths

- Comprehensive tab structure: Auth, Query, Upload, SQL Approval, History, Eval Dashboard
- Real-time feature detection via OpenAPI schema inspection
- Eval dashboard with comparison between eval runs, per-golden drill-down, RAGAS metrics
- SQL approval workflow properly integrated with LangGraph interrupt pattern
- Good UX for developer testing: preset use cases, feature toggles, response detail expansion

#### Limitations

**Responsiveness:** Streamlit is not responsive by default. All layouts use fixed column ratios that break on mobile screens. `layout="wide"` is forced.

**Authentication storage:** JWT token stored in `st.session_state` — cleared on browser refresh. Users must re-login every session.

**Upload endpoint mismatch:** The upload tab calls `/documents/upload` which doesn't exist in the FastAPI app. This tab is completely non-functional.

**Hardcoded defaults:** Login form pre-fills `agent@demo.local`/`demo1234` — production-unfriendly.

**No real-time updates:** SQL approval requires manual tab switching. No WebSocket or SSE for async notifications.

**Slow feedback:** All queries use synchronous `requests` calls with a 600-second timeout. Long queries just show a spinner with no progress indication.

**State management:** `st.session_state` is the only state mechanism. Complex state flows (pending SQL, last result) are brittle across tab switches.

#### UX Issues

- Feature toggles are in a collapsible expander that defaults to open — takes too much vertical space
- Eval dashboard is powerful but overwhelming for new users
- No dark mode
- Badge HTML is injected via `unsafe_allow_html=True` — a Streamlit anti-pattern
- History tab shows last 20 queries but with no way to replay them

#### What Should Eventually Be Replaced

The entire Streamlit app should be replaced with a proper React/Next.js SaaS frontend for production use. The Streamlit app is an excellent developer testing harness but has fundamental architectural limitations for end-user deployment:
- No multi-tenancy
- No role-based UI (admin vs user)
- No streaming responses
- No notification system for SQL approvals
- Cannot be embedded or white-labeled

---

## 15. Documentation Review

### README.md

Well-written with architecture diagrams, feature tables, quick-start instructions, and API documentation. Covers all major features. Has badges for all major dependencies.

**Gaps:**
- Does not mention that `psycopg[binary]` must be installed separately
- Does not mention that `local_storage.py` is not implemented
- The upload endpoint is documented in the README but does not exist
- Security architecture describes 9 layers but the numbering in the code is different from the README numbering

### Comments and Docstrings

Inconsistent coverage:
- `llm_service.py` — no docstrings, minimal comments
- `rag_service.py` — some inline comments, no function docstrings
- `crag.py` — clear function names, no docstrings
- `query_cache_service.py` — reasonably documented
- `graph.py` — has docstrings on node functions
- `security/` modules — mostly self-documenting via clear function names

**No module-level docstrings** anywhere. No type hints on some internal functions.

### Architecture Documentation

`PROJECT_REPORT.md` exists but has not been reviewed in detail. The README covers architecture well. No formal ADR (Architecture Decision Records) exist.

### Missing Documentation

- No API schema documentation beyond Swagger auto-gen
- No database schema documentation
- No runbook for operating the service in production
- No deployment guide
- No contributing guide
- No changelog

---

## 16. File Classification

| File | Classification | Reason |
|---|---|---|
| `app/main.py` | KEEP | Minimal and correct |
| `app/config.py` | REFACTOR | Dead Vanna settings, trailing whitespace |
| `app/models.py` | REFACTOR | Duplicate injection validators; merge into shared validator |
| `app/core/graph.py` | REFACTOR | Duplicate logic with rag_service; dead state fields; duck-typed Chunk |
| `app/core/state.py` | REFACTOR | Several fields are never populated by graph nodes |
| `app/api/query.py` | KEEP | Core endpoint logic is clean |
| `app/api/auth.py` | REFACTOR | Untyped dict body; no connection pooling |
| `app/api/admin.py` | KEEP | Health check logic is appropriate |
| `app/middleware/auth.py` | KEEP | JWT logic is solid |
| `app/middleware/rate_limiter.py` | REFACTOR | No graceful degradation when Redis is down |
| `app/security/content_moderation.py` | KEEP | Well-structured |
| `app/security/input_guard.py` | KEEP | Well-structured |
| `app/security/input_restructuring.py` | KEEP | Naming of `summarize_text` is misleading but logic is fine |
| `app/security/output_validator.py` | INVESTIGATE | Never wired into main flow — dead code or future use |
| `app/security/spotlighting.py` | KEEP | Clean and effective |
| `app/security/system_prompt.py` | REFACTOR | JSON response format asked but not enforced |
| `app/security/token_budget.py` | REFACTOR | No graceful degradation when Redis is down |
| `app/services/crag.py` | KEEP | Clean implementation |
| `app/services/doc_cache_service.py` | KEEP | Good abstraction; broken only because local_storage is empty |
| `app/services/document_processor.py` | REFACTOR | MPS accelerator hardcoded (Apple Silicon only) |
| `app/services/embedding_service.py` | KEEP | Cache integration is clean |
| `app/services/hyde.py` | KEEP | Well implemented |
| `app/services/llm_service.py` | KEEP | Simple and clean |
| `app/services/query_cache_service.py` | REFACTOR | Redis clear is a no-op; stats are in-memory only |
| `app/services/rag_service.py` | REFACTOR | Too many responsibilities; duplicate intent classification |
| `app/services/reranking.py` | REFACTOR | Model instance not shared across requests |
| `app/services/router_service.py` | REFACTOR | Irrelevant domain hints in `_DOCUMENT_HINTS` |
| `app/services/self_reflective.py` | KEEP | Clean Self-RAG implementation |
| `app/services/sparse_vector_service.py` | REFACTOR | No index caching |
| `app/services/sql_service.py` | REFACTOR | SQLService instantiated multiple times losing schema cache |
| `app/services/vector_store.py` | REFACTOR | `_build_sparse_index` called inline every time |
| `app/services/web_search.py` | KEEP | Simple and clean |
| `app/storage/storage_backend.py` | KEEP | Good abstraction |
| `app/storage/local_storage.py` | INVESTIGATE | Empty file — must be implemented or removed |
| `app/storage/s3_storage.py` | KEEP | Full implementation |
| `eval/` (all files) | KEEP | Evaluation harness is a key asset |
| `eval/seed_questions.yaml` | KEEP | 40 validated golden questions — high value |
| `notebooks/` | OPTIONAL | Research artifacts; not production code |
| `scripts/streamlit_app.py` | REFACTOR | 1,337 lines; should be split into modules |
| `scripts/seed_db.py` | KEEP | Essential for setup |
| `scripts/serve.py` | KEEP | Simple launcher |
| `seed/docs/true_data/` | KEEP | K8s documentation corpus |
| `seed/migrations/*.sql` | KEEP | Database schema |
| `pyproject.toml` | REFACTOR | Missing `psycopg[binary]`; dead Vanna dep |
| `Dockerfile` | REFACTOR | Should add `psycopg[binary]` to pyproject.toml instead |
| `docker-compose.yml` | REFACTOR | No Redis service; no `--reload` flag for dev |
| `Makefile` | REFACTOR | References non-existent scripts |
| `.env.example` | KEEP | Well documented |
| `uv.lock` | KEEP | Locked deps |
| `README.md` | REFACTOR | Docs gaps around missing endpoint, storage |

---

## 17. Technical Debt

### High Priority

| Issue | Location | Impact |
|---|---|---|
| `local_storage.py` is empty | `app/storage/local_storage.py` | Breaks `DocCacheService` with local backend |
| `psycopg[binary]` not in `pyproject.toml` | `pyproject.toml`, `Dockerfile` | Silent install breakage |
| Sparse index rebuilt on every request | `vector_store.py:_build_sparse_index()` | Severe latency on hybrid/sparse queries |
| `Reranker` model not shared across requests | `rag_service.py`, `reranking.py` | Cold-start latency per request |
| `/documents/upload` endpoint missing | `app/api/` | Streamlit upload tab non-functional |
| Redis `clear()` is a no-op for Redis tier | `query_cache_service.py` | Admin cache clear silently fails |
| SQL approval not user-scoped | `api/query.py:/query/sql/execute` | Any user can resume any SQL thread |
| `is_select_only()` incomplete guard | `sql_service.py` | Potential SQL injection in edge cases |

### Medium Priority

| Issue | Location | Impact |
|---|---|---|
| Duplicate logic: graph nodes vs rag_service | `graph.py`, `rag_service.py` | Maintenance drift; double intent classification |
| `SQLService` instantiated multiple times | `rag_service.py` | Schema cache never hits |
| Irrelevant domain hints in router | `router_service.py:_DOCUMENT_HINTS` | Wrong domain bypasses LLM classification |
| `generate()` used where `generate_with_json()` needed | `rag_service.py` | JSON output not enforced |
| No connection pooling for Postgres auth | `auth.py` | Per-request connection overhead |
| Rate limiter not graceful on Redis failure | `rate_limiter.py` | Security bypass if Redis is down |
| `output_validator.py` is unwired | `security/output_validator.py` | Dead code or orphaned feature |
| No startup validation of `jwt_secret` | `config.py` | Placeholder secret could go to production |
| Double `classify_intent()` calls | `rag_service.py`, `graph.py` | Wasted LLM/Redis calls |
| CrossEncoder model loading per-call | `reranking.py` | 2–5s cold start not amortized |

### Low Priority

| Issue | Location | Impact |
|---|---|---|
| `cost_saved` always `"$0.00"` | `api/query.py` | Misleading metric |
| `confidence` is hardcoded | `rag_service.py` | Not a real confidence score |
| Duck-typed Chunk creation | `graph.py:58` | Code smell; should use `RetrievedChunk` |
| `bcrypt` imported directly | `middleware/auth.py` | Bypasses passlib abstraction |
| Trailing blank lines in `config.py` | `app/config.py` | Minor cleanliness |
| `finalize()` is a no-op node | `graph.py` | Unnecessary node |
| In-memory cache stats not useful at scale | `query_cache_service.py` | Misleading in multi-process deployments |
| No `tests/` directory | project root | Can't run `make test` |
| `make seed-data` references missing scripts | `Makefile` | Command fails with no error message |
| MPS accelerator hardcoded in document processor | `document_processor.py` | Silently falls back to CPU in Docker |
| `run_rag_with_trace_no_cache` alias | `rag_service.py` | Misleading name — still uses cache |

---

## 18. Risks

### Scalability Risks

| Risk | Severity | Notes |
|---|---|---|
| Sparse index rebuild is O(n×d) per request | CRITICAL | Unbounded growth with corpus size |
| Single Postgres connection for LangGraph | HIGH | Not pool-safe under concurrent load |
| In-process TF-IDF model | HIGH | Can't scale horizontally without sticky sessions |
| HyDE + Self-RAG worst case: 9 LLM calls | HIGH | Cost and latency explosion with all features enabled |
| In-memory cache stats don't aggregate | MEDIUM | Multi-replica deployments give misleading stats |
| No Qdrant payload indexes | MEDIUM | Filtered searches slow at scale |

### Security Risks

| Risk | Severity | Notes |
|---|---|---|
| No SQL injection protection beyond keyword check | HIGH | `is_select_only()` can be bypassed |
| Rate limiting disabled when Redis is down | HIGH | Complete bypass during Redis outage |
| SQL approval not user-scoped | HIGH | Cross-user SQL execution possible |
| JWT secret has no startup validation | MEDIUM | Default placeholder could reach production |
| `/admin/health` is public | MEDIUM | Reveals service topology |
| PII redaction blocks valid K8s IPs | LOW | Reduces answer quality for networking questions |

### Deployment Risks

| Risk | Severity | Notes |
|---|---|---|
| `psycopg[binary]` not in pyproject.toml | HIGH | Fresh install from pyproject.toml fails |
| `local_storage.py` empty | HIGH | Upload functionality broken locally |
| No data pipeline scripts | MEDIUM | `make seed-data` fails; noisy corpus empty |
| Missing migration 002 reference | MEDIUM | migration comment references non-existent file |
| Docker image ~2–3 GB | LOW | Slow builds; can be optimized |

### Maintenance Risks

| Risk | Severity | Notes |
|---|---|---|
| Dual execution paths (graph vs rag_service) | HIGH | Changes must be synchronized in two places |
| No tests | HIGH | No regression protection |
| 1,337-line Streamlit file | MEDIUM | Hard to maintain or onboard new developers |
| Notebooks are not tested | LOW | May bit-rot against current API |

### Developer Experience Risks

| Risk | Severity | Notes |
|---|---|---|
| No local Redis (docker-compose uses Upstash) | HIGH | Can't fully develop offline |
| HyDE cold start (model downloads) | MEDIUM | First-run document upload takes 1–3 minutes |
| `make seed-data` fails silently | MEDIUM | No corpus → no useful results |

---

## 19. Refactoring Opportunities

Listed only. Do not implement in Phase 0.

1. **Extract upload endpoint** — implement `POST /documents/upload` in `admin.py` using existing `DocumentProcessor`, `DocCacheService`, `embed_texts`, `upsert_chunks`
2. **Implement `local_storage.py`** — filesystem-backed `StorageBackend` using `pathlib.Path`
3. **Singleton sparse index** — cache `SparseVectorIndex` at module level with background refresh on document upsert
4. **Singleton Reranker** — module-level `_reranker` instance so CrossEncoder model stays in memory
5. **Singleton SQLService** — one instance with a valid `_schema_context` cache across all requests
6. **Add `psycopg[binary]` to `pyproject.toml`** — and remove from Dockerfile
7. **Unify RAG execution path** — remove inline SQL/hybrid code from `rag_service.py` and have it delegate to graph nodes, or remove the graph-level nodes and route everything through `rag_service.py`
8. **Fix Redis clear** — use `SCAN`+`DEL` with namespace prefixes or maintain a key registry
9. **User-scope SQL approval** — store `user_id` in LangGraph state and validate in `/query/sql/execute`
10. **Merge duplicate injection validators** — single shared `validate_message` function used by both `ChatRequest` and `QueryRequest`
11. **Fix `_DOCUMENT_HINTS`** — replace irrelevant ML paper terms with Kubernetes-relevant hint shortcuts
12. **Add Postgres connection pool** — `psycopg2.pool.ThreadedConnectionPool` for auth and SQL endpoints
13. **Wire `output_validator.py`** — use `validate_with_retry` in the RAG answer generation path
14. **Enforce JSON response format** — use `generate_with_json()` for the answer generation call in `rag_service._generate()`
15. **Split `streamlit_app.py`** into page modules: `auth_page.py`, `query_page.py`, `upload_page.py`, `sql_page.py`, `eval_page.py`
16. **Add JWT startup validation** — raise at startup if `jwt_secret` is the default placeholder
17. **Real confidence scores** — compute from CRAG relevance score, reranker top score, or reflection score
18. **Real cost tracking** — compute `cost_saved` from embedding cache hits × token cost
19. **Add `tests/` directory** — pytest unit tests for security layers, cache service, intent router, SQL validation
20. **Remove Vanna dependency** — not used; `vanna[openai,postgres]` is a large unused dep
21. **Add `/health` (public, lightweight)** — simple liveness probe without infrastructure details
22. **Protect `/admin/health`** with at minimum basic auth or restrict to internal networks
23. **Add API versioning prefix** — `/v1/` prefix on all routes for future versioning

---

## 20. Final Summary

### What Parts Are Excellent?

- **The multi-tier cache architecture** is sophisticated and well-designed. SHA-256 keys, graceful Redis fallback, and separate TTLs per tier are all correct engineering decisions.
- **The security layer design** (9 distinct layers including spotlighting, input restructuring, output moderation, token budget) is genuinely enterprise-grade and shows deep thinking about LLM security.
- **The evaluation harness** (40 golden questions, RAGAS metrics, feature profiles, forbidden-keyword checks, Streamlit dashboard) is outstanding. This level of systematic RAG evaluation is rare in codebase of this size.
- **The human-in-the-loop SQL approval** via LangGraph `interrupt()` is a thoughtful and correct safety feature for Text2SQL.
- **The CRAG pipeline** is clean, well-tested against golden questions, and correctly handles all edge cases (empty chunks, disabled, web fallback failure).
- **The Self-RAG reflection prompt** is detailed and well-engineered, with clear scoring criteria and strict standards.

### What Parts Are Over-Engineered?

- **LangGraph for this workflow:** The graph has only 7 nodes with mostly linear flows. The primary benefit is the interrupt mechanism for SQL approval. The added complexity of graph state, checkpointing, and psycopg v3/v2 mixing is high overhead for this use case. A simpler async service with a pending-SQL Redis queue would achieve the same result with less infrastructure.
- **The dual execution paths (graph + rag_service):** Having both the LangGraph nodes and `rag_service.py` implement full intent routing independently is significant accidental complexity.
- **`GraphState` with 22 fields:** Many fields are never actually populated by graph nodes; they are set inside `rag_service.py` and never surfaced to the graph state machine.

### What Parts Are Under-Engineered?

- **`local_storage.py`** — empty. The storage abstraction is well-designed but the local backend doesn't exist.
- **`/documents/upload` endpoint** — Streamlit calls it; FastAPI doesn't have it. Core feature missing.
- **Connection pooling** — every auth request and SQL query opens and closes a new Postgres connection.
- **Sparse index caching** — the most impactful performance fix, completely absent.
- **Tests** — zero test coverage despite a `pyproject.toml` testpath declaration.
- **`is_select_only()` SQL guard** — a minimal keyword check when parameterized queries or a proper SQL parser would be safer.

### Which Modules Should Never Be Rewritten?

- `eval/seed_questions.yaml` — 40 carefully validated golden questions with expected sources, keywords, and feature tags. This is a research artifact, not code.
- `app/security/system_prompt.py` — the hardened system prompt is carefully crafted; changes should be deliberate and tested against the eval harness.
- `app/services/query_cache_service.py` — the two-tier cache with SHA-256 keys and tier-specific TTLs is correct; refactor for Redis clear, not for architecture.
- `app/services/crag.py` — clean, correct, well-tested.

### Which Modules Require the Biggest Redesign?

1. **`app/services/rag_service.py`** — needs to either delegate to graph nodes or replace them entirely. Cannot remain a parallel implementation of the same logic.
2. **`app/core/graph.py`** — the graph-level SQL approval is the only unique value. The routing and retrieval nodes are redundant with `rag_service.py`. Needs consolidation.
3. **`app/services/vector_store.py` + `app/services/sparse_vector_service.py`** — the hybrid search implementation needs an in-process singleton sparse index with background invalidation.
4. **`scripts/streamlit_app.py`** — 1,337-line monolith that needs splitting into modules; eventually replaced with a proper SaaS frontend.
5. **`app/api/auth.py`** — untyped body dict, no connection pooling, no password validation.
