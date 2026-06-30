# API_INTEGRATION_GUIDE.md — VectraIQ Phase 4

## Overview

All backend communication goes through `frontend/src/lib/api.ts`. This file provides:
- TypeScript interfaces that mirror backend Pydantic models
- A generic `request<T>()` fetch wrapper with auth injection and error normalization
- Three API namespaces: `authApi`, `queryApi`, `adminApi`
- An SSE async generator for streaming responses

---

## Backend Base URL

```typescript
const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
```

Set `NEXT_PUBLIC_API_URL` in `.env.local` to change the target. The value must be the backend's origin (e.g., `http://localhost:8000` locally, `https://api.vectraiq.com` in production).

---

## Authentication

The API client reads the JWT from Zustand's persisted store:

```typescript
function getToken(): string | null {
  try {
    const raw = localStorage.getItem("vectraiq_auth");
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed?.state?.token ?? null;
  } catch {
    return null;
  }
}
```

Every request to a protected endpoint receives `Authorization: Bearer <token>` injected by `request<T>()`.

---

## Error Handling

All non-2xx responses are parsed and thrown as `VectraIQAPIError`:

```typescript
class VectraIQAPIError extends Error {
  code: string;
  httpStatus: number;
  details?: unknown;
  requestId?: string;
}
```

The `code` field maps to a user-facing message via `friendlyError(code)` in `lib/utils.ts`. Error codes that are mapped:

| Code | User message |
|---|---|
| `auth/invalid-credentials` | Invalid username or password |
| `auth/token-expired` | Your session has expired — please sign in again |
| `auth/insufficient-permissions` | You don't have permission to do this |
| `rate-limit/exceeded` | You've sent too many requests — please wait a moment |
| `budget/exceeded` | Daily token budget reached |
| `input/rejected` | Your input was flagged by the content filter |
| `input/too-long` | Input exceeds the maximum length |
| `sql/execution-failed` | The SQL query failed to execute |
| `retrieval/no-results` | No relevant documents found |
| `network` | Cannot reach VectraIQ — check your connection |

Any unmapped code falls back to the raw error message.

---

## Type Definitions

```typescript
// Auth
interface TokenResponse {
  access_token: string;
  token_type: string;
}

// Query
interface QueryRequest {
  question: string;
  search_mode?: "dense" | "sparse" | "hybrid";
  top_k?: number;
  enable_rerank?: boolean;
  enable_hyde?: boolean;
  enable_crag?: boolean;
  enable_self_reflective?: boolean;
  thread_id?: string;
}

interface ChatResponse {
  answer: string;
  sources: string[];
  intent: string;
  confidence: number;
  cache_hit: boolean;
  metadata: ResponseMetadata;
  pending_sql?: PendingSQLBlock;
}

interface PendingSQLBlock {
  thread_id: string;
  sql: string;
  schema_context: string;
}

interface ResponseMetadata {
  latency_ms: number;
  tokens_used: number;
  model: string;
  search_mode: string;
  chunks_retrieved: number;
  reranked: boolean;
  hyde_used: boolean;
  crag_used: boolean;
}

// Admin
interface ServiceHealth {
  status: "ok" | "degraded";
  openai: boolean;
  qdrant: boolean;
  postgres: boolean;
  redis: boolean;
  tavily: boolean;
}

interface CacheTierStats {
  hits: number;
  misses: number;
  hit_rate: number;
}

type CacheStatsResponse = Record<string, CacheTierStats>;

interface CacheClearResponse {
  cleared: string[];
}

// SSE streaming
type StreamEvent =
  | { event: "status"; data: { stage: string; message: string } }
  | { event: "result"; data: ChatResponse }
  | { event: "error"; data: { code: string; message: string } }
  | { event: "done"; data: Record<string, never> };
```

---

## API Methods

### `authApi`

```typescript
authApi.login(username: string, password: string): Promise<TokenResponse>
```
Posts `application/x-www-form-urlencoded` to `POST /auth/token`. The backend expects `grant_type=password` OAuth2 form fields.

```typescript
authApi.register(username: string, password: string): Promise<{ message: string }>
```
Posts JSON to `POST /auth/register`.

---

### `queryApi`

```typescript
queryApi.ask(body: QueryRequest): Promise<ChatResponse>
```
Posts to `POST /query` (non-streaming). Returns full `ChatResponse`.

```typescript
queryApi.approveSql(threadId: string): Promise<ChatResponse>
```
Posts to `POST /query/sql/execute` with `{ thread_id: threadId }`. Resumes a LangGraph interrupted thread and returns the completed response.

```typescript
queryApi.stream(body: QueryRequest): AsyncGenerator<StreamEvent>
```
Posts to `POST /query/stream`. Reads the `ReadableStream` from the response body line-by-line, parsing SSE `event:` and `data:` fields. Yields typed `StreamEvent` objects.

**SSE frame format:**
```
event: status
data: {"stage": "routing", "message": "Classifying intent…"}

event: result
data: {"answer": "...", "sources": [...], ...}

event: done
data: {}
```

---

### `adminApi`

```typescript
adminApi.health(): Promise<ServiceHealth>
```
`GET /admin/health`. Returns HTTP 200 when all critical services are up, HTTP 503 when degraded (Phase 4 fix). TanStack Query treats 503 as an error by default — the health query uses `retry: false` to avoid retrying on degraded state.

```typescript
adminApi.cacheStats(): Promise<CacheStatsResponse>
```
`GET /admin/cache/stats`. Returns per-tier hit/miss counters.

```typescript
adminApi.cacheClear(): Promise<CacheClearResponse>
```
`POST /admin/cache/clear`. Clears the in-memory LRU cache. Redis entries are unaffected (Upstash HTTP API limitation — documented in the response `cleared` array).

---

## TanStack Query Integration

### Setup (`components/providers.tsx`)

```typescript
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});
```

### Query Keys Convention

```typescript
["health"]          // ServiceHealth — refetchInterval: 30s
["cache-stats"]     // CacheStatsResponse — refetchInterval: 60s
```

Mutations (cache clear, SQL approve) do not have query keys. After `cacheClear` succeeds, `qc.invalidateQueries({ queryKey: ["cache-stats"] })` forces a fresh fetch.

---

## Streaming SSE Pattern

The `queryApi.stream()` generator is consumed in `useChat.sendMessage()`:

```typescript
for await (const event of queryApi.stream(body)) {
  chatStore.handleStreamEvent(event);
  if (event.event === "done") break;
}
```

`handleStreamEvent` in the chat store dispatches:
- `status` → updates `streamStage` on the placeholder assistant message
- `result` → replaces placeholder content with full ChatResponse fields
- `error` → sets error content on placeholder, marks `streaming: false`
- `done` → marks placeholder `streaming: false`

---

## Backend Endpoints Reference

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/auth/token` | No | Login (OAuth2 password flow) |
| POST | `/auth/register` | No | Register new user |
| POST | `/query` | JWT | Ask question (blocking) |
| POST | `/query/stream` | JWT | Ask question (SSE streaming) |
| POST | `/query/sql/execute` | JWT | Resume SQL approval thread |
| GET | `/admin/health` | JWT | Service health check |
| GET | `/admin/cache/stats` | JWT | Per-tier cache stats |
| POST | `/admin/cache/clear` | JWT + admin | Clear in-memory cache |
| POST | `/documents/upload` | JWT | Upload document (**not yet implemented**) |

---

## Local Development

1. Start backend: `make api` (FastAPI at `:8000`)
2. Start frontend: `cd frontend && npm run dev` (Next.js at `:3000`)
3. Backend CORS is configured to allow `http://localhost:3000` via `FRONTEND_ORIGINS` env var (Phase 4 fix)
4. No proxy needed in local dev — `NEXT_PUBLIC_API_URL=http://localhost:8000` in `.env.local`

---

## Production Deployment

Set `FRONTEND_ORIGINS=https://app.vectraiq.com` on the backend and `NEXT_PUBLIC_API_URL=https://api.vectraiq.com` on the frontend build. The Next.js API proxy (`/api/backend/*`) is available as an alternative to direct CORS if the deployment topology requires it.
