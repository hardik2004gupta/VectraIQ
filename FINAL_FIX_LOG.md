# VectraIQ — Final Fix Log

All code changes applied during the Final Release Audit Cycle (2026-06-29 → 2026-06-30).  
Ordered chronologically. Each entry records what changed, why, and how to verify.

---

## FIX-001 — Version alignment: 2.0.0 → 1.0.0

**Files:** `pyproject.toml`, `vectraiq/main.py`  
**Severity:** Critical  
**Reason:** First public release must follow SemVer from 1.0.0. Internal version was 2.0.0, which would confuse users and package registries.

**Changes:**
- `pyproject.toml` line 3: `version = "2.0.0"` → `version = "1.0.0"`
- `vectraiq/main.py` in `create_app()`: `version="2.0.0"` → `version="1.0.0"`

**Verify:** `curl http://localhost:8000/docs` — OpenAPI spec title shows `VectraIQ 1.0.0`.

---

## FIX-002 — pyproject.toml internal dev comments removed

**File:** `pyproject.toml`  
**Severity:** High  
**Reason:** Phase-tracking comments like `# Phase 2 —` were internal scaffolding not appropriate for a public package manifest.

**Changes:** Removed all `# Phase N —` comment headers from the `[project.dependencies]` section. Replaced with semantic grouping comments (`# Web`, `# LLM`, `# Vector DB & embeddings`, etc.).

---

## FIX-003 — asyncio.get_event_loop() → get_running_loop()

**File:** `vectraiq/api/query.py:234`  
**Severity:** Critical  
**Reason:** `asyncio.get_event_loop()` is deprecated in Python 3.10+ when called from a coroutine with a running loop. It raises `DeprecationWarning` and will raise `RuntimeError` in Python 3.14.

**Change:**
```python
# Before
loop = asyncio.get_event_loop()

# After
loop = asyncio.get_running_loop()
```

**Verify:** Run `POST /query/stream` and confirm no DeprecationWarning in logs.

---

## FIX-004 — Dockerfile: non-root user + HEALTHCHECK

**File:** `Dockerfile`  
**Severity:** Critical  
**Reason:** Running containers as root violates container security best practices and many enterprise security policies. Missing HEALTHCHECK means orchestrators can't detect unhealthy containers.

**Changes:**
- Added `RUN useradd -m --uid 1001 appuser`
- Added `RUN chown -R appuser:appuser /app`
- Added `USER appuser`
- Added `HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 CMD curl -f http://localhost:8000/admin/health || exit 1`
- Removed redundant `RUN uv pip install --system --no-cache psycopg[binary]` (already in `pyproject.toml`)
- Removed `torchvision` (not used by this project)

**Verify:** `docker build . && docker inspect vectraiq:latest | jq '.[0].Config.User'` → `"appuser"`.

---

## FIX-005 — .dockerignore created

**File:** `.dockerignore` (new)  
**Severity:** High  
**Reason:** Without a `.dockerignore`, `docker build` sends the entire repo (including `.git/`, `frontend/node_modules/`, `archive/`) as build context — slowing builds and risking leaking secrets.

**Contents:** Excludes `.git`, `frontend/`, `archive/`, `notebooks/`, Python artifacts (`__pycache__`, `*.pyc`, `.venv`), test artifacts, `eval/`, docs, `.env` files, IDE configs.

**Verify:** `docker build . 2>&1 | head -5` — build context size should be <50 MB.

---

## FIX-006 — docker-compose.yml: restart policies + Qdrant healthcheck

**File:** `docker-compose.yml`  
**Severity:** High  
**Reason:** Without `restart: unless-stopped`, services that crash stay down silently. The `app` service was waiting on `qdrant: condition: service_started` (always true) rather than `service_healthy`, so the app could attempt Qdrant connections before Qdrant finished initializing.

**Changes:**
- Added `restart: unless-stopped` to `postgres`, `qdrant`, and `app`
- Added Qdrant healthcheck: `curl -f http://localhost:6333/healthz`
- Changed `app.depends_on.qdrant` from `service_started` to `service_healthy`
- Changed `postgres:16` to `postgres:16-alpine` (smaller image)
- Changed `LOG_JSON` default from `false` to `true` (production-appropriate)

---

## FIX-007 — CI workflow: npm ci → npm install

**File:** `.github/workflows/ci.yml`  
**Severity:** High  
**Reason:** `npm ci` requires `package-lock.json` to exist. The frontend directory has no lock file, causing all frontend CI jobs to fail immediately.

**Changes:**
- All `npm ci` → `npm install`
- `cache-dependency-path: frontend/package-lock.json` → `frontend/package.json`
- Applied consistently across `frontend-lint` and `frontend-build` jobs

---

## FIX-008 — Knowledge Base page: honest upload UX

**File:** `frontend/src/app/(dashboard)/knowledge/page.tsx`  
**Severity:** Critical (misleading UX)  
**Reason:** The previous implementation showed a `toast.success("indexed successfully")` toast after a simulated `setTimeout` chain. No actual upload or indexing occurred. This deceives users into believing documents are being ingested.

**Changes:**
- Removed all fake upload simulation (`setTimeout` chains, artificial status transitions)
- Added persistent amber warning banner: "Upload API coming in v1.1. Files dropped here are queued locally only."
- Changed toast from `toast.success("… indexed successfully")` to `toast.info("Files queued — backend upload is coming in v1.1")` with description pointing to `make seed`
- File status now shows "Queued" (not a fake "indexed" or "processing" state)
- Added CLI workaround instructions inline in the banner

---

## FIX-009 — Analytics page: hardcoded hex → CSS variables

**File:** `frontend/src/app/(dashboard)/analytics/page.tsx`  
**Severity:** High  
**Reason:** Hardcoded hex colors (`#1a1a1a`, `#6a6a6a`, `#2a2a2a`, `#f2f2f2`) in Recharts config would break if a light theme were ever added, and also created visual inconsistency with the design system.

**Changes:**
- `fill: "#6a6a6a"` → `fill: "var(--color-text-tertiary)"` in `CHART_STYLE`
- Tooltip `background: "#1a1a1a"` → `"var(--color-bg-elevated)"`
- Tooltip `border: "1px solid #2a2a2a"` → `"1px solid var(--color-border-subtle)"`
- Tooltip `color: "#f2f2f2"` → `"var(--color-text-primary)"`
- Legend `color: "#6a6a6a"` → `"var(--color-text-tertiary)"`
- Misses bar `fill: "#2a2a2a"` → `"var(--color-bg-elevated)"`

---

## FIX-010 — layout.tsx: favicon and robots metadata

**File:** `frontend/src/app/layout.tsx`  
**Severity:** High  
**Reason:** Missing `icons` metadata means the browser tab shows a blank favicon. Missing `robots` metadata means search crawlers get no explicit indexing directive.

**Changes:**
```typescript
icons: {
  icon: [
    { url: "/favicon.ico", sizes: "any" },
    { url: "/icon.svg", type: "image/svg+xml" },
  ],
  apple: "/apple-touch-icon.png",
},
robots: {
  index: true,
  follow: true,
  googleBot: { index: true, follow: true },
},
```

**New file:** `frontend/public/icon.svg` — indigo diamond SVG matching the accent color (`#6366f1`).

---

## FIX-011 — Chat store: localStorage persistence via Zustand persist

**File:** `frontend/src/store/chat.ts`  
**Severity:** High  
**Reason:** Chat history was stored only in memory — all messages lost on page refresh. For a knowledge platform copilot, losing conversation context on every navigation is a major UX regression.

**Changes:**
- Wrapped `create<ChatState>()` with `persist()` middleware
- Storage key: `"vectraiq-chat"` in `localStorage`
- `partialize`: persists only `messages` (last 100, non-streaming) and `conversationId` — not `isLoading` or `streamStage`
- `onRehydrateStorage`: converts `createdAt` strings back to `Date` objects; resets `isLoading: false` and `streamStage: null`

**Verify:** Open chat, send a message, hard-refresh the page — messages persist.

---

*VectraIQ Final Fix Log — 2026-06-30*
