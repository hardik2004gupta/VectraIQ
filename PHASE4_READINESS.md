# PHASE4_READINESS.md — VectraIQ Phase 3.5

**Audit date:** 2026-06-30  
**Question:** Is the backend ready to support Next.js frontend development?  
**Verdict: Conditionally ready — fix 3 items first, then start Phase 4**

---

## Summary Table

| Area | Status | Blocker? |
|---|---|---|
| API shape & stability | ✅ Stable | No |
| Auth flow (JWT bearer) | ✅ Working | No |
| CORS configuration | ❌ Broken | **YES** |
| Error envelope consistency | ✅ Standardized | No |
| OpenAPI schema | ✅ Auto-generated | No |
| Response types | ✅ Pydantic models | No |
| Streaming endpoint | ❌ Missing | For chat UX |
| Token refresh | ❌ Missing | For long sessions |
| File upload endpoint | ❌ Missing | For admin features |
| Request correlation ID | ✅ `X-Request-ID` | No |
| SQL approval flow | ✅ Working | No |
| Pagination | N/A | No list endpoints yet |

---

## Blocker 1 — CORS Must Be Fixed Before Day 1

**Current config:**
```python
CORSMiddleware(allow_origins=["*"], allow_credentials=True, ...)
```

The CORS specification (Fetch Standard §3.2.5) forbids wildcard origin with credentialed requests. Every browser API call that includes `Authorization: Bearer <token>` will be rejected with a CORS preflight error.

**Fix (15 minutes):**
```python
# config.py — add:
frontend_origins: list[str] = ["http://localhost:3000"]

# main.py — change:
CORSMiddleware(
    allow_origins=settings.frontend_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)
```

Add `FRONTEND_ORIGINS=http://localhost:3000,https://app.vectraiq.io` to `.env.example`.

**This must be done before writing a single frontend API call.**

---

## Blocker 2 — Streaming Is Needed for Chat UX

**Current state:** `POST /query` is a blocking endpoint. It returns after the full LLM generation completes. For complex hybrid queries, this means 8–22 seconds of silence before any response appears.

**Impact:** In a chat UI, users will see a loading spinner for 8–22 seconds with no feedback. This is unacceptable UX for a conversational interface.

**Recommendation:** Add `GET /query/stream` or `POST /query/stream` as a Server-Sent Events endpoint before building any chat frontend component. The existing `/query` endpoint can remain as-is for programmatic clients.

**Minimum viable streaming:**
```python
@router.post("/query/stream")
async def query_stream(body: QueryRequest, user: User = Depends(get_current_user)):
    async def event_generator():
        yield f"data: {json.dumps({'type': 'status', 'message': 'Processing...'})}\n\n"
        # ... call pipeline, yield partial results ...
        yield f"data: {json.dumps({'type': 'answer', 'text': answer})}\n\n"
        yield "data: [DONE]\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

**This is a "must-have before Chat component" but not a Day 1 blocker.**

---

## Blocker 3 — Token Refresh for Long Sessions

**Current state:** JWTs have a configurable TTL (`JWT_EXPIRATION_MINUTES`, default likely 60). No refresh endpoint exists. When a token expires, the frontend must redirect to login.

**Impact:** For a K8s operations tool where engineers might have the UI open for hours, frequent re-authentication is disruptive.

**Minimum fix:** Add `POST /auth/refresh` that accepts a valid (non-expired) token and returns a new one with a fresh expiry. This is a 30-minute addition.

---

## What the Frontend Can Build Today

These features are immediately buildable without backend changes:

### ✅ Login Page
- `POST /auth/login` with `{username, password}` → `{token, token_type, expires_in}`
- Store JWT in `localStorage` or `httpOnly` cookie
- All auth errors return the standard `ErrorResponse` envelope

### ✅ Registration Page
- `POST /auth/register` → same response as login
- `409 ConflictError` for duplicate username
- `429 RateLimitError` for too many registrations

### ✅ Admin Health Dashboard
- `GET /admin/health` → `ServiceHealth` (qdrant, postgres, redis, openai, tavily statuses)
- No auth required (good for a status page)

### ✅ Admin Cache Stats Page
- `GET /admin/cache/stats` → `CacheStatsResponse` with hit rates per tier
- Requires admin JWT

### ✅ Admin Cache Clear Button
- `POST /admin/cache/clear` → `{cleared: [...], message: "..."}`
- Requires admin JWT

### ✅ Question/Answer Page (non-chat)
- `POST /query` → `ChatResponse` with `answer`, `sources`, `confidence`, `cache_hit`, `request_id`
- Full feature flags available: `search_mode`, `enable_rerank`, `enable_hyde`, `enable_crag`, `enable_self_reflective`
- Metadata: `retrieval_count`, `search_mode`, `reranked`, `crag_triggered`, `reflection_score`

### ✅ SQL Approval Flow
- After a query returns `pending_sql` block (non-null), show the SQL to the user
- `POST /query/sql/execute` with `{query_id: string, approved: boolean}`
- Returns final `ChatResponse` with the SQL result

### ✅ Error Handling
All errors share the same `ErrorResponse` shape:
```typescript
interface ErrorResponse {
  error: {
    code: string;     // machine-readable: "rate_limit_exceeded", "injection_detected", etc.
    message: string;  // human-readable
    details: Record<string, unknown>;
  };
  request_id: string;
}
```

The frontend can handle every error type with a single error handler, then route on `error.code` for specific messages.

---

## API Contract for Frontend

### Authentication Header
```
Authorization: Bearer <jwt_token>
```
All `/query` and `/admin` endpoints require this header (except `GET /admin/health`).

### All Endpoints

| Method | Path | Auth Required | Response |
|---|---|---|---|
| POST | `/auth/register` | No | `TokenResponse` |
| POST | `/auth/login` | No | `TokenResponse` |
| POST | `/query` | Yes | `ChatResponse` |
| POST | `/query/sql/execute` | Yes | `ChatResponse` |
| GET | `/admin/health` | No | `ServiceHealth` |
| GET | `/admin/cache/stats` | Admin | `CacheStatsResponse` |
| POST | `/admin/cache/clear` | Admin | `{"cleared": [...], "message": str}` |

### TypeScript Types (auto-generate from OpenAPI or write manually)

```typescript
interface QueryRequest {
  question: string;            // 1–2000 chars
  top_k?: number;              // 1–50, default 5
  search_mode?: "dense" | "sparse" | "hybrid";  // default "dense"
  enable_rerank?: boolean;     // default false
  enable_hyde?: boolean;       // default false
  enable_crag?: boolean;       // default true
  enable_self_reflective?: boolean;  // default false
}

interface PendingSQLBlock {
  thread_id: string;
  sql: string;
  explanation: string;
}

interface ResponseMetadata {
  retrieval_count: number;
  search_mode: string;
  reranked: boolean;
  crag_triggered: boolean;
  reflection_score: number | null;
}

interface ChatResponse {
  answer: string;
  sources: string[];
  confidence: number;
  pending_sql: PendingSQLBlock | null;
  cache_hit: boolean;
  request_id: string;
  metadata: ResponseMetadata;
}

interface ServiceHealth {
  status: "ok" | "degraded";
  qdrant: boolean;
  postgres: boolean;
  redis: boolean;
  openai: boolean;
  tavily: boolean;
}
```

---

## Important Notes for Frontend Development

### Request Correlation
Include `X-Request-ID: <uuid>` in requests OR use the auto-generated one from the response. This ID appears in `ChatResponse.request_id` and all error envelopes. Use it to correlate frontend error reports with backend logs.

### SQL Approval UX
When `ChatResponse.pending_sql` is non-null:
1. Display `pending_sql.sql` and `pending_sql.explanation` to the user
2. User clicks Approve or Reject
3. `POST /query/sql/execute` with `{query_id: pending_sql.thread_id, approved: true/false}`
4. Response is a new `ChatResponse` with the executed result

**Note:** SQL approval is not currently user-scoped (TD-005). Any authenticated user can approve any query_id. This should be fixed before exposing the SQL approval UI to multiple users.

### Confidence Field
`ChatResponse.confidence` is currently hardcoded (0.7 for RAG, 0.8 for hybrid, 0.9 for SQL). Do not display this as a percentage to users — it does not represent actual retrieval confidence. Either omit from the UI or display as "low/medium/high" tiers.

### Cache Hit Indicator
`ChatResponse.cache_hit: boolean` — when true, the answer was served from the 5-tier cache. Good for a subtle "⚡ Cached" badge in the UI.

### Source Attribution
`ChatResponse.sources: string[]` — list of document names (not URLs). These are filenames from the Kubernetes documentation corpus (e.g., `k8s_pods.md`, `persistent_volumes.txt`). Display as citation chips, not clickable links (no URLs available from the current backend).

### Error Code Mapping (for i18n/UX)
```typescript
const ERROR_MESSAGES: Record<string, string> = {
  "injection_detected": "Your message was blocked by our security filter. Please rephrase.",
  "content_blocked": "Your message was blocked for policy reasons.",
  "rate_limit_exceeded": "You're sending too many requests. Please wait a moment.",
  "token_budget_exceeded": "You've reached your daily usage limit.",
  "authentication_error": "Your session has expired. Please log in again.",
  "token_expired": "Your session has expired. Please log in again.",
  "authorization_error": "You don't have permission to perform this action.",
  "validation_error": "Please check your input and try again.",
};
```

---

## Phase 4 Start Conditions

**Required before writing frontend code:**
- [ ] TD-004: CORS wildcard replaced with explicit origins
- [ ] Local backend runs successfully (`uv sync` + `make api` works)

**Required before merging Chat component:**
- [ ] Streaming endpoint (`/query/stream`) added
- [ ] TD-005: SQL approval user-scoping fixed

**Required before production launch:**
- [ ] TD-001, TD-002: Dockerfile and compose fixed
- [ ] TD-003: psycopg[binary] added to pyproject.toml
- [ ] TD-006: JWT secret minimum-length validation
- [ ] TD-007: Basic test suite
- [ ] TD-009: Sparse index caching
- [ ] TD-016: README updated

---

## Verdict

**Start Phase 4 after fixing CORS (TD-004).** This is a 15-minute fix. Everything else can be done in parallel with frontend development.

The API shape is stable and well-documented. The error envelope is consistent. The auth flow is correct. The OpenAPI schema at `/docs` is complete and accurate. A frontend developer can start building Login, Registration, Admin Health, and the basic Q&A page immediately after CORS is fixed.

Add the streaming endpoint in the first week of Phase 4 — before building the main chat interface component.
