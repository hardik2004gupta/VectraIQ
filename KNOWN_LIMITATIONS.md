# VectraIQ v1.0.0 — Known Limitations

This document describes the known limitations of VectraIQ v1.0.0. These are not bugs — they are architectural constraints, deferred features, or intentional scope decisions for the initial release. Each entry includes the impact and planned resolution.

---

## L-01 — Sparse index rebuilt on every hybrid/sparse query

**Impact:** Performance  
**Severity:** Medium  
**Area:** `vectraiq/services/sparse_vector_service.py`

The TF-IDF sparse index is fitted from scratch on every hybrid or sparse retrieval call. This involves scrolling up to 10,000 documents from Qdrant and running `TfidfVectorizer.fit_transform()` in-process.

**Effect:** Adds 500ms–3s latency per query depending on corpus size. CPU-bound; blocks the async event loop via `run_in_executor`.

**Planned fix (v1.1):** Cache the fitted vectorizer and document term matrix in Redis on first build; invalidate on document ingestion. Alternatively, migrate to Qdrant's native sparse vector support (SPLADE/BM25).

---

## L-02 — LangGraph graph initialized at import time

**Impact:** Startup / Testing  
**Severity:** Low  
**Area:** `vectraiq/core/graph.py`

The `graph = build_graph()` call at module level requires a live PostgreSQL connection at import time. If Postgres is unavailable when the module is first imported, the process will crash before the FastAPI lifespan can report a useful error.

**Effect:** Cold-start failures are opaque; unit tests that import `graph.py` must have Postgres available or mock `PostgresSaver`.

**Planned fix (v1.1):** Lazily initialize the graph inside the FastAPI lifespan handler; use a module-level `Optional` with a `get_graph()` accessor.

---

## L-03 — No database connection pooling in auth routes

**Impact:** Performance / Scalability  
**Severity:** Medium  
**Area:** `vectraiq/api/auth.py`, `vectraiq/api/admin.py`

Auth and admin routes open a new `psycopg2.connect()` connection per request using context managers. Under load, this creates and destroys database connections at the request rate, saturating Postgres's `max_connections` (default 100).

**Effect:** Auth endpoints are a scalability bottleneck above ~50 concurrent users.

**Planned fix (v1.1):** Introduce `psycopg2.pool.ThreadedConnectionPool` or migrate auth to use the same async SQLAlchemy pool used elsewhere.

---

## L-04 — Document upload API not implemented

**Impact:** Features  
**Severity:** Medium  
**Area:** `vectraiq/api/` (missing endpoint), `frontend/src/app/(dashboard)/knowledge/page.tsx`

The `POST /documents/upload` endpoint does not exist. The Knowledge Base page in the UI allows users to select or drag-and-drop files, but files are only queued locally in the browser — they are not ingested into the knowledge base.

**Workaround:** Place documents in `seed/docs/true_data/` and run `make seed`. The Docling-based ingestion pipeline processes PDF, DOCX, HTML, TXT, and Markdown.

**Planned fix (v1.1):** Implement `POST /documents/upload` with multipart form handling, Docling parsing, chunking, embedding, and Qdrant upsert. Wire to the frontend Knowledge Base page.

---

## L-05 — SQL approval not scoped per user

**Impact:** Security  
**Severity:** Medium  
**Area:** `vectraiq/api/query.py` (`POST /query/sql/execute`)

The LangGraph `PostgresSaver` stores SQL approval threads by `thread_id`. Any authenticated user who knows (or guesses) a `thread_id` can resume and approve another user's SQL query.

**Effect:** In a multi-tenant deployment, users could approve SQL generated for other users' contexts.

**Planned fix (v1.1):** Store the originating `user_id` alongside the thread in Postgres; verify `user_id` matches on `/query/sql/execute`.

---

## L-06 — Redis cache.clear() is a no-op for Upstash

**Impact:** Operations  
**Severity:** Low  
**Area:** `vectraiq/services/query_cache_service.py`

The Upstash HTTP SDK does not expose a `FLUSHDB` command in its Python client. Calling `cache.clear()` (e.g., from the admin API) only clears the in-memory LRU layer — the Redis-backed tiers are not affected.

**Effect:** Cache invalidation via the admin endpoint is incomplete. Stale entries in Redis will expire naturally per their TTL (7d embedding, 1h RAG, 24h SQL gen, 15m SQL result).

**Workaround:** Use the Upstash dashboard to flush the database, or set `UPSTASH_REDIS_URL` to empty to run in-memory-only mode.

**Planned fix (v1.2):** Implement key-prefix-based deletion (`SCAN` + `DEL`) as a workaround for Upstash's missing `FLUSHDB`.

---

## L-07 — No test suite

**Impact:** CI / Reliability  
**Severity:** Low  
**Area:** `tests/` (directory exists, no test files)

The `pyproject.toml` and CI workflow reference `tests/` but no unit or integration tests exist. The CI `backend-tests` job runs `pytest tests/` and passes vacuously.

**Effect:** No automated regression detection for backend code changes.

**Planned fix (v1.1):** Write unit tests for security layers, cache service, RAG service (with mocked Qdrant), and auth endpoints. Target 60% line coverage for v1.1.

---

## L-08 — No package-lock.json for frontend

**Impact:** CI / Reproducibility  
**Severity:** Low  
**Area:** `frontend/`

The `frontend/` directory does not have a committed `package-lock.json`. CI uses `npm install` (not `npm ci`), which resolves packages at install time and is non-reproducible across runs.

**Effect:** A transitive dependency update could break the frontend build unexpectedly between CI runs.

**Planned fix:** Run `npm install` once with a clean `node_modules/`, commit the resulting `package-lock.json`, and change CI back to `npm ci`.

---

## L-09 — Reranker loaded per-request if not singleton

**Impact:** Performance  
**Severity:** Low  
**Area:** `vectraiq/services/reranking.py`

If `Reranker()` is instantiated inside request handlers rather than at module level, the CrossEncoder model (sentence-transformers) is loaded from disk on every request that requires reranking.

**Effect:** 1–3 second startup cost per reranked request; high memory churn.

**Current state:** A module-level singleton pattern is used in `reranking.py`. Verify this is not broken by future refactors.

---

## L-10 — No distributed tracing (OpenTelemetry)

**Impact:** Observability  
**Severity:** Low  
**Area:** Infrastructure

The project uses structured JSON logging (Loguru) and a health endpoint but does not emit OpenTelemetry traces. Latency breakdown across RAG pipeline stages is not observable in production without adding OTel instrumentation.

**Planned fix (v1.2):** Add `opentelemetry-sdk` + `opentelemetry-instrumentation-fastapi` + `opentelemetry-instrumentation-httpx`; export to Jaeger or Tempo.

---

*VectraIQ Known Limitations — v1.0.0 — 2026-06-30*
