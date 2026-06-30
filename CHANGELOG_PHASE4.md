# CHANGELOG_PHASE4.md — VectraIQ Phase 4

**Date:** 2026-06-30  
**Branch:** master  
**Scope:** Backend stabilization (Part A) + Frontend build (Part B)

---

## Part A — Backend Stabilization

### TD-001 · Dockerfile copies wrong package directory
**File:** `Dockerfile`  
**Change:** `COPY app/ ./app/` → `COPY vectraiq/ ./vectraiq/`  
**Impact:** Docker builds were broken after Phase 2 renamed `app/` to `vectraiq/`. The container started with an empty module, causing immediate ImportError on startup.

---

### TD-002 · docker-compose volume mount points to old directory
**File:** `docker-compose.yml`  
**Change:** `./app:/app/app` → `./vectraiq:/app/vectraiq`  
**Impact:** Hot-reload volume was shadowing the installed package with an empty directory.

---

### TD-003 · docker-compose database name inconsistency
**File:** `docker-compose.yml`  
**Change:** `POSTGRES_DB: adv_rag` → `POSTGRES_DB: vectraiq`; `DATABASE_URL` updated to match.  
**Impact:** Aligns the compose environment with the new project name. `adv_rag` was the original pre-rename name.

---

### TD-004 · CORS wildcard incompatible with credentialed requests
**Files:** `vectraiq/config.py`, `vectraiq/main.py`, `docker-compose.yml`  
**Change:**
- Added `frontend_origins: list[str] = ["http://localhost:3000"]` to `Settings`
- `CORSMiddleware` now uses `allow_origins=settings.frontend_origins` (was `["*"]`)
- Explicit allowed methods and headers: `GET POST PUT DELETE OPTIONS`, `Authorization Content-Type X-Request-ID`
- Added `FRONTEND_ORIGINS=${FRONTEND_ORIGINS:-http://localhost:3000}` to docker-compose app service env
**Impact:** Browsers block `fetch` with `credentials: "include"` when `allow_origins=["*"]`. This caused every authenticated frontend request to be rejected. Per spec, explicit origins are required when `allow_credentials=True`.

---

### TD-005 · `psycopg[binary]` (v3) missing from pyproject.toml
**File:** `pyproject.toml`  
**Change:** Added `"psycopg[binary]>=3.1"` to `[project.dependencies]`  
**Impact:** Installing from pyproject.toml alone failed to include the LangGraph `PostgresSaver` dependency. It was only present in `Dockerfile` via a manual `pip install`. Non-Docker local installs broke silently.

---

### TD-006 · `scikit-learn` undeclared dependency
**File:** `pyproject.toml`  
**Change:** Added `"scikit-learn>=1.4"` to `[project.dependencies]`  
**Impact:** `sparse_vector_service.py` and `vector_store.py` import sklearn. It was not declared and could silently be absent in fresh environments.

---

### TD-007 · Sparse index rebuilt on every hybrid/sparse query
**File:** `vectraiq/ai/vector_store.py`  
**Change:** Added module-level sparse index cache with 30-minute TTL:
```python
_sparse_index: SparseVectorIndex | None = None
_sparse_index_built_at: float = 0.0
_SPARSE_INDEX_TTL_SECONDS: float = 1800.0

def _get_sparse_index() -> SparseVectorIndex:
    global _sparse_index, _sparse_index_built_at
    now = time.time()
    if _sparse_index is None or (now - _sparse_index_built_at) > _SPARSE_INDEX_TTL_SECONDS:
        _sparse_index = _build_sparse_index()
        _sparse_index_built_at = now
    return _sparse_index
```
Added `invalidate_sparse_index()` called after `upsert_chunks()`. Added module-level `QdrantClient` singleton to avoid reconnecting on every call.  
**Impact:** Previously, every sparse or hybrid search scrolled 10,000 Qdrant documents and re-fit TF-IDF. This was a major latency bottleneck for the UI. Queries now reuse the in-memory index until TTL expires or new documents are uploaded.

---

### TD-008 · Health endpoint returns HTTP 200 when degraded
**File:** `vectraiq/api/admin.py`  
**Change:** 
```python
http_status = status.HTTP_200_OK if all_critical_ok else status.HTTP_503_SERVICE_UNAVAILABLE
return JSONResponse(status_code=http_status, content=health.model_dump())
```
**Impact:** Frontend health polling could not distinguish healthy from degraded state by status code. Dashboard and Settings pages now correctly show "degraded" status without needing to inspect the JSON body.

---

### TD-009 · Hybrid answer path bypasses hardened system prompt
**File:** `vectraiq/core/graph.py`  
**Change:** Added `from vectraiq.security.system_prompt import build_system_prompt` import. In `_generate_hybrid_answer`, prepend `build_system_prompt()` to the synthesis prompt.  
**Impact:** The RAG and SQL paths used the hardened system prompt with behavioral rules and domain restrictions. The hybrid synthesis path constructed a plain prompt, bypassing all security preambles.

---

### TD-010 · No SSE streaming endpoint
**File:** `vectraiq/api/query.py`  
**Change:** Added `POST /query/stream` endpoint:
- Returns `StreamingResponse` with `media_type="text/event-stream"`
- Yields SSE frames: `event: status`, `event: result`, `event: error`, `event: done`
- Runs `graph.invoke()` in a thread pool via `asyncio.get_event_loop().run_in_executor()` to avoid blocking the ASGI event loop
- Full security pipeline (llm-guard, PII redaction, rate limit, token budget) applied identically to blocking `/query` endpoint
**Impact:** Without streaming, the chat UI had to wait for the full LangGraph pipeline to complete (often 5–15 seconds) before showing any response. SSE allows the frontend to display intermediate status messages and stream the final answer progressively.

---

### TD-011 · docker-compose app healthcheck missing
**File:** `docker-compose.yml`  
**Change:** Added healthcheck to the `app` service:
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/admin/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```
**Impact:** Docker Compose had no way to know when the app was ready. Dependent services (or CI) could start making requests before the app had connected to Postgres and Qdrant.

---

## Part B — Frontend

### FE-001 · Next.js 15 application scaffolded
Created `frontend/` directory with Next.js 15, React 19, TypeScript (strict), Tailwind CSS v4, and all required dependencies.

Key config files:
- `package.json` — full dependency manifest
- `next.config.ts` — Turbopack, API proxy `/api/backend/*`
- `tsconfig.json` — strict mode, `@/*` path alias
- `postcss.config.mjs` — `@tailwindcss/postcss`
- `.env.local.example`

---

### FE-002 · Design system
**File:** `frontend/src/app/globals.css`  
Complete dark-mode design system using Tailwind v4 `@theme` block with CSS custom properties:
- Background scale (5 levels, `#080808` → `#222222`)
- Border scale (3 levels)
- Text scale (4 levels)
- Accent color system (indigo `#6366f1` with light/dark/glow variants)
- Semantic colors (success, warning, error, info)
- Utility classes: `.glass`, `.gradient-text`, `.gradient-accent`, `.glow-accent`
- CSS animations: shimmer (skeleton), pulse-dot (typing), fade-in-up, spin

---

### FE-003 · Typed API client
**File:** `frontend/src/lib/api.ts`  
Full typed client covering all backend endpoints. Includes `VectraIQAPIError` class, `getToken()` reading from Zustand persist storage, and `queryApi.stream()` SSE async generator.

---

### FE-004 · Auth store + chat store
**Files:** `frontend/src/store/auth.ts`, `frontend/src/store/chat.ts`  
- `authStore`: Zustand with `persist` middleware. Stores token, username, isAdmin, expiry. `isAuthenticated()` checks expiry and auto-clears.
- `chatStore`: Messages array with `ChatMessage` type, `handleStreamEvent()` dispatcher for SSE events.

---

### FE-005 · Auth hooks
**File:** `frontend/src/hooks/useAuth.ts`  
`login()` decodes JWT payload (base64url) client-side to extract `sub` and `is_admin`. Handles toast notifications and routing.

---

### FE-006 · Chat hook with streaming
**File:** `frontend/src/hooks/useChat.ts`  
`sendMessage()` consumes `queryApi.stream()` async generator. `approveSql()` calls `queryApi.approveSql()` and updates the relevant message in the store.

---

### FE-007 · Shared component library
Built 9 shared components covering all UI needs:
- `Button` (5 variants, loading state)
- `Card` + `StatCard`
- `StatusBadge` + `ServiceDot`
- `Skeleton`, `CardSkeleton`, `MessageSkeleton`, `TableRowSkeleton`
- `EmptyState`
- `MarkdownRenderer` (GFM, syntax highlighting, copy button)

---

### FE-008 · Layout components
- `Sidebar`: Fixed nav with Framer Motion shared layout animation for active indicator
- `PageHeader`: Title + description + actions slot

---

### FE-009 · Chat components
- `ChatMessage`: User/assistant/SQL approval rendering, sources, action bar
- `ChatInput`: Auto-resize textarea, settings panel (search mode, top_k, feature toggles)
- `TypingIndicator`: Animated dots with stage label

---

### FE-010 · Pages

| Page | Route | Description |
|---|---|---|
| Landing | `/` | Hero, features, FAQ, tech stack, CTA |
| Login | `/login` | JWT login form with Zod validation |
| Register | `/register` | Registration with password strength meter |
| Dashboard | `/dashboard` | Health bar, StatCards, quick actions |
| Chat | `/chat` | Streaming chat with auto-scroll, example prompts |
| Knowledge Base | `/knowledge` | Dropzone UI, animated file list (backend endpoint pending) |
| Analytics | `/analytics` | BarChart + PieChart from Recharts, per-tier hit rate bars |
| Settings | `/settings` | Health grid, API config, cache management, account |

---

## Known Outstanding Issues

| ID | Issue | Severity | Notes |
|---|---|---|---|
| KB-001 | `/documents/upload` endpoint missing in backend | High | Knowledge Base page simulates state locally. Backend implementation required. |
| SQL-001 | SQL approval not user-scoped | Medium | Any authenticated user can resume any SQL thread. Backend fix required. |
| CACHE-001 | Redis `cache.clear()` is a no-op | Low | Only in-memory cache is cleared. Documented in Settings page. |
| AUTH-001 | No refresh token flow | Low | Expired JWT causes silent logout on next page load. |
| SPARSE-001 | Sparse index TTL is process-global | Low | Multi-worker deployments (Gunicorn) will build one index per worker. Acceptable for now. |
