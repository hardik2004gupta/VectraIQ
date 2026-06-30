# VectraIQ v2 — Implementation Roadmap
**Version:** 2.0  
**Status:** Design Phase  

**Rule:** Each phase must leave the project in a working, testable state. No "half-finished" phases.

---

## Phase Overview

```
Phase 0 (Completed)  → Audit
Phase 1 (In Progress)→ Architecture Design

Phase 2  → Critical Bug Fixes         ~1 week   project works correctly
Phase 3  → Clean Architecture         ~2 weeks  maintainable structure
Phase 4  → AI Improvements            ~1 week   better AI performance
Phase 5  → Frontend                   ~2 weeks  modern SaaS UI
Phase 6  → Production Hardening       ~1 week   deploy-ready
```

---

## Phase 2 — Critical Bug Fixes

**Goal:** Fix the bugs that silently break existing functionality. No refactoring.  
**Branch:** `fix/critical-bugs`  
**Duration:** ~1 week  
**Test signal:** All existing streamlit features work correctly after this phase.

### Fix 2.1 — Implement `local_storage.py`

**Problem:** `app/storage/local_storage.py` is an empty file. Any code path that tries to use local storage silently fails.

**Action:** Implement `LocalStorageBackend` with `save()`, `load()`, `delete()`, `exists()`, `list()` using `pathlib.Path`.

**Test:** Upload a document with `STORAGE_BACKEND=local` and verify it is saved and retrievable.

---

### Fix 2.2 — Reranker as Singleton

**Problem:** `Reranker()` is instantiated on every request, causing CrossEncoder model reload (~1–3s cold start) per query.

**Action:** Move `Reranker()` instantiation to module-level or app startup. Inject as dependency.

**Test:** Query latency drops by 1–3 seconds on second query.

---

### Fix 2.3 — Sparse Index as Singleton

**Problem:** `_build_sparse_index()` scrolls 10,000 Qdrant documents on every hybrid query.

**Action:** Build index once at startup. Refresh in background after document upserts.

**Test:** Hybrid query latency drops from ~5s to <1s on warm path.

---

### Fix 2.4 — Fix SQLService Singleton

**Problem:** `SQLService` is instantiated multiple times, losing the schema cache each time.

**Action:** Make SQLService a singleton. Schema inspection runs once and is cached.

**Test:** Second SQL query completes without re-introspecting `information_schema`.

---

### Fix 2.5 — Fix Redis Cache Clear

**Problem:** `QueryCacheService.clear()` has `pass` for the Redis tier — clearing cache only clears in-memory, leaving Redis stale.

**Action:** Implement SCAN + DEL in batches of 100. Use keyspace prefix for each namespace.

**Test:** After `clear()`, Redis DBSIZE decreases. Subsequent query hits backend, not cache.

---

### Fix 2.6 — User-Scoped SQL Approval

**Problem:** Any authenticated user can resume any thread ID to approve/execute SQL — not scoped to the requesting user.

**Action:** Store `user_id` in LangGraph checkpoint state. On resume, validate `checkpoint.state["user_id"] == requesting_user_id`. Reject with 403 if mismatch.

**Test:** User A cannot approve User B's SQL thread. User A can approve their own.

---

### Fix 2.7 — Fix IP Redaction in PII Scanner

**Problem:** `content_moderation.py` redacts IP addresses, breaking Kubernetes networking answers (e.g., "Pod IP is 10.0.0.5").

**Action:** Remove IPv4/IPv6 patterns from PII redaction. K8s IPs are operational data, not PII.

**Test:** Query "What is the IP of pod nginx-abc?" returns answer with actual IP addresses visible.

---

### Fix 2.8 — Wire `output_validator.py`

**Problem:** `validate_with_retry()` is implemented but never called in any production code path.

**Action:** Call `output_validator.validate_with_retry(answer)` in `rag_service.py` before returning response.

**Test:** Feed an answer that violates output rules. Verify retry fires and corrected answer is returned.

---

### Fix 2.9 — Fix `is_select_only()` Guard

**Problem:** Current regex is incomplete — doesn't catch multi-statement via semicolons or comments that strip to DDL.

**Action:** Implement robust SQL validation: strip comments, split on unquoted semicolons, check each statement starts with SELECT.

**Test:** `DROP TABLE users` → rejected. `SELECT 1; DROP TABLE users` → rejected. `/* comment */ SELECT 1` → allowed.

---

### Fix 2.10 — Fix psycopg Version Conflict

**Problem:** `app/api/auth.py` imports psycopg2 while `app/core/graph.py` uses psycopg v3. Mixed versions.

**Action:** Replace all `import psycopg2` with `import psycopg` (v3). Update connection string format.

**Test:** Auth endpoint works. LangGraph checkpoint works. No import errors.

---

## Phase 3 — Clean Architecture

**Goal:** Restructure into the monorepo layout defined in `FOLDER_STRUCTURE.md`. No new features.  
**Branch:** `refactor/clean-architecture`  
**Duration:** ~2 weeks  
**Test signal:** All Phase 2 tests still pass. New unit tests cover domain + use case layers.

### Step 3.1 — Monorepo Structure

Create `apps/api/src/` directory hierarchy as defined in `FOLDER_STRUCTURE.md`. Move existing fixed files into place one module at a time, updating import paths.

Order (dependencies first):
1. `core/settings.py` (Settings class with validators)
2. `core/startup.py` (pre-flight checks)
3. `domain/entities/` (Chunk, Document, User)
4. `domain/repositories/` (abstract interfaces)
5. `infrastructure/` (concrete implementations)
6. `ai/` modules (use infrastructure interfaces)
7. `application/use_cases/` (use AI + infrastructure)
8. `api/v1/routers/` (thin HTTP layer)
9. `main.py` (lifespan + router registration)

### Step 3.2 — Dependency Injection

Replace module-level globals and service instantiation inside functions with:
- FastAPI lifespan builds all singletons
- `core/dependencies.py` exposes them via `Depends()`
- All routers receive services via DI, not direct imports

### Step 3.3 — Remove Dual Execution Path

`rag_service.py` has `_run_sql_inline` and `_run_hybrid_inline` duplicating `graph.py` node logic. Remove the inline paths. All queries go through the LangGraph graph.

### Step 3.4 — Remove Duplicate Intent Classification

`rag_service.py` classifies intent, then `graph.py` does it again. Remove from rag_service. Single classification in the `classify_intent` graph node.

### Step 3.5 — API Versioning

Move all routes to `/api/v1/` prefix. Update streamlit app to use new paths.

### Step 3.6 — Remove Vanna Dependency

Remove from `pyproject.toml`. `SQLService` does not use Vanna — it does custom Text2SQL. Remove the dead import.

### Step 3.7 — Add psycopg v3 to pyproject.toml

Add `psycopg[binary]>=3.1` to dependencies. Remove any psycopg2 entries.

### Step 3.8 — Settings Validation

Add `@model_validator(mode='after')` to Settings:
- `jwt_secret` must be ≥ 32 characters
- `storage_backend` must be one of: `local`, `s3`, `r2`
- Startup fails fast with clear error message if misconfigured

### Step 3.9 — Unit Tests for Core Layers

Write unit tests for:
- `domain/entities/` — validation edge cases
- `application/use_cases/` — with repository mocks
- `ai/sql/sql_validator.py` — 20+ SQL injection test cases
- `ai/security/pii_redactor.py` — verify IPs are NOT redacted
- `core/settings.py` — JWT_SECRET length validation

---

## Phase 4 — AI Improvements

**Goal:** Implement the AI architecture improvements from `AI_ARCHITECTURE.md`. No structural changes.  
**Branch:** `feat/ai-improvements`  
**Duration:** ~1 week  
**Test signal:** Golden eval suite shows improvement over Phase 2 baseline.

### Step 4.1 — LangGraph v2 Graph

Implement 10-node graph from `AI_ARCHITECTURE.md`:
- `classify_intent` → `check_cache` → `retrieve` → `rerank` → `generate` → `validate_output` → `check_self_rag` → `finalize`
- SQL path: `generate_sql` → `await_sql_approval` → `execute_sql` → `finalize`
- Remove no-op `finalize()` node from v1

### Step 4.2 — HyDE with Content-Hash RRF

Update `HyDERetriever` to use content hash (SHA-256 of chunk text) as RRF key instead of raw text. Prevents key collisions.

### Step 4.3 — GraphState Cleanup

Replace 22-field TypedDict (8 fields unpopulated) with 20-field v2 state where all fields are populated by graph nodes. Add `user_id` field.

### Step 4.4 — Eval Baseline

Run `python eval/run_eval.py --profile all` and save results to `eval/results/phase4_baseline.json`. This is the comparison baseline for all future changes.

### Step 4.5 — Domain-Agnostic Router Prompt

Replace `_DOCUMENT_HINTS` list in `router_service.py` that contains irrelevant ML paper terms (gsm8k, humaneval, qkv) with the domain-agnostic intent classification prompt from `AI_ARCHITECTURE.md`.

---

## Phase 5 — Frontend

**Goal:** Build the Next.js 14 frontend from `FRONTEND_BLUEPRINT.md`.  
**Branch:** `feat/frontend`  
**Duration:** ~2 weeks  
**Test signal:** All pages render. Chat flow works end-to-end. Document upload works. SQL approval works.

### Step 5.1 — Monorepo Setup

```
apps/web/
  package.json
  tsconfig.json
  tailwind.config.ts
  next.config.ts
  src/app/
  src/components/
  src/lib/
  src/store/
  src/types/
```

Install: Next.js 14, shadcn/ui, Framer Motion, Zustand, TanStack Query, Lucide React, Recharts.

### Step 5.2 — Auth Pages

- `/login` — username + password form
- `/register` — registration form
- JWT stored in httpOnly cookie via BFF API route

### Step 5.3 — Application Shell

- Sidebar with navigation
- Layout with sidebar + main content
- Dark mode (default) with light mode toggle
- `Cmd+K` command palette

### Step 5.4 — Chat Interface

- Message thread rendering (user + AI bubbles)
- SSE streaming integration
- Feature toggle chips (hybrid, rerank, crag, hyde, self_rag)
- SQL Approval card component
- Source expansion panels
- Markdown rendering with syntax highlighting

### Step 5.5 — Documents Page

- File list table with status badges
- Upload drag-and-drop dialog
- Progress tracking during processing

### Step 5.6 — Dashboard and Analytics

- KPI cards (queries, cache rate, latency)
- Route distribution donut chart
- Query volume line chart (Recharts)
- System status panel

### Step 5.7 — Replace Streamlit

Once the Next.js frontend passes manual testing:
- Archive `scripts/streamlit_app.py` to `scripts/legacy/streamlit_app.py`
- Update `README.md` to point to Next.js frontend
- Remove streamlit from dev dependencies

### Step 5.8 — E2E Tests

Playwright tests for:
- Login → chat → receive answer
- Upload document → index → query
- SQL approval flow
- Feature toggles persist after refresh

---

## Phase 6 — Production Hardening

**Goal:** Make VectraIQ deploy-ready. Security, observability, CI/CD.  
**Branch:** `feat/production`  
**Duration:** ~1 week  
**Test signal:** Deployed to Railway + Vercel. Health checks pass. Eval suite runs in CI.

### Step 6.1 — GitHub Actions CI

Create `.github/workflows/ci.yml`:
- lint-api (ruff + mypy)
- lint-web (eslint + tsc)
- test-api (pytest with real Postgres + Qdrant via Docker)
- test-web (Vitest)
- Deploy on push to main

### Step 6.2 — Eval in CI

Create `.github/workflows/eval.yml`:
- Weekly scheduled run
- `python eval/run_eval.py --profile all`
- Fail if answer_relevance drops >5% vs stored baseline

### Step 6.3 — Structured Logging

Replace bare `print()` statements with loguru:
- JSON format in production
- Human-readable in development
- `trace_id` propagated through all layers
- LLM call logging (model, tokens used, latency)

### Step 6.4 — Health Checks

`GET /api/v1/health` pings Postgres, Qdrant, Redis in parallel. Returns:
```json
{ "status": "ok", "services": { "postgres": "ok", "qdrant": "ok", "redis": "ok" }, "latency_ms": 45 }
```

### Step 6.5 — Graceful Degradation Audit

Verify each external service has graceful behavior when down:
- Redis down → rate limiter allows request (log warning); cache miss (fallback to backend)
- Qdrant down → 503 with clear error
- OpenAI down → 503 with retry hint
- Tavily down → skip CRAG web fallback, use local results only

### Step 6.6 — Pre-Deployment Checklist

```
☐ JWT_SECRET is ≥ 32 chars random value (not placeholder)
☐ CORS origin matches actual frontend URL
☐ LLM_GUARD_ENABLED=true in production
☐ ENVIRONMENT=production set
☐ Qdrant collection exists with correct vector dimensions
☐ Postgres migrations applied
☐ Demo data seeded (seed_db.py)
☐ Health check passes
☐ Frontend NEXT_PUBLIC_API_URL points to Railway URL
☐ SSE endpoint accessible (no Vercel edge timeout conflicts)
```

---

## Testing Strategy Summary

| Layer | Framework | Real Services? | Coverage Target |
|---|---|---|---|
| Domain entities | pytest | No | 90% |
| Application use cases | pytest | Mocked repos | 80% |
| AI modules (unit) | pytest | Mocked LLM | 70% |
| AI modules (integration) | pytest | Real Qdrant + Postgres | Key paths |
| API routes | pytest + httpx | Test client | All routes |
| Frontend components | Vitest | No | 70% |
| E2E | Playwright | Full stack | Critical flows |
| Golden eval | Custom script | Full stack | 40 questions |

**Key rule inherited from v1 lesson:** Do NOT mock database in integration tests. Prior incident: mock tests passed while prod migration failed.

---

## Phase Exit Criteria

| Phase | Done When... |
|---|---|
| Phase 2 | All 10 bug fixes have passing tests. streamlit_app.py works without errors. |
| Phase 3 | Monorepo structure complete. All imports resolve. All Phase 2 tests pass in new structure. |
| Phase 4 | Eval baseline saved. `hybrid+rerank+crag` profile answer_relevance ≥ 0.75. |
| Phase 5 | Playwright e2e tests pass. No console errors. Chat + Documents + Dashboard work. |
| Phase 6 | Deployed to Railway + Vercel. CI green. Health checks pass. Eval runs in CI. |
