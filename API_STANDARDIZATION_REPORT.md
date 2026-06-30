# API_STANDARDIZATION_REPORT.md — VectraIQ Phase 3

## Error Envelope

Every error response now has a consistent shape regardless of which layer caught it:

```json
{
  "error": {
    "code": "rate_limit_exceeded",
    "message": "Rate limit exceeded. Please retry later.",
    "details": {}
  },
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

| Field | Type | Description |
|---|---|---|
| `error.code` | string | Machine-readable error code (see Error Codes below) |
| `error.message` | string | Human-readable explanation |
| `error.details` | object | Optional structured detail (e.g. `field_errors` for validation) |
| `request_id` | string | Correlates to X-Request-ID header and server logs |

---

## Error Codes

| Code | HTTP Status | Trigger |
|---|---|---|
| `authentication_error` | 401 | Missing or invalid JWT |
| `token_expired` | 401 | JWT has expired |
| `authorization_error` | 403 | Authenticated user lacks required role |
| `rate_limit_exceeded` | 429 | Per-user or per-IP rate limit exceeded |
| `token_budget_exceeded` | 429 | Daily token budget exhausted |
| `injection_detected` | 400 | Prompt injection pattern found in input |
| `content_blocked` | 400 | Content blocked by moderation policy |
| `validation_error` | 422 | Pydantic request model validation failure |
| `sql_generation_error` | 422 | SQL could not be generated or is not SELECT-only |
| `ai_provider_error` | 502 | OpenAI / LLM call failed |
| `vector_store_error` | 503 | Qdrant unavailable |
| `database_error` | 503 | PostgreSQL unavailable |
| `not_found` | 404 | Resource not found |
| `conflict` | 409 | Resource already exists (e.g. duplicate username) |
| `internal_error` | 500 | Unexpected server error |

---

## Endpoint Inventory

### Query

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/query` | Bearer JWT | Submit a natural language question |
| POST | `/query/sql/execute` | Bearer JWT | Approve or reject a pending SQL statement |

### Auth

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/register` | None (rate limited by IP) | Create a new user account |
| POST | `/auth/login` | None (rate limited by IP) | Authenticate and receive a JWT |

### Admin

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/admin/health` | None | Dependency health check |
| GET | `/admin/cache/stats` | Bearer JWT (admin) | Per-tier cache statistics |
| POST | `/admin/cache/clear` | Bearer JWT (admin) | Clear in-memory cache |

---

## Request Models

### `POST /query` — `QueryRequest`

```json
{
  "question": "How do I restart a crashed Kubernetes pod?",
  "top_k": 5,
  "search_mode": "dense",
  "enable_rerank": false,
  "enable_hyde": false,
  "enable_crag": true,
  "enable_self_reflective": false
}
```

| Field | Type | Default | Constraints |
|---|---|---|---|
| `question` | string | required | 1–2000 chars, injection-checked |
| `top_k` | int | 5 | 1–50 |
| `search_mode` | enum | "dense" | "dense" \| "sparse" \| "hybrid" |
| `enable_rerank` | bool | false | — |
| `enable_hyde` | bool | false | — |
| `enable_crag` | bool | true | — |
| `enable_self_reflective` | bool | false | — |

### `POST /query/sql/execute` — `SqlApprovalRequest`

```json
{
  "query_id": "550e8400-e29b-41d4-a716-446655440000",
  "approved": true
}
```

### `POST /auth/register` and `POST /auth/login` — `AuthRequest`

```json
{
  "username": "sre-operator",
  "password": "securepassword123"
}
```

---

## Response Models

### `ChatResponse` (from `/query` and `/query/sql/execute`)

```json
{
  "answer": "To restart a crashed pod, use: kubectl rollout restart ...",
  "sources": ["kubernetes-pods.md", "troubleshooting-guide.md"],
  "confidence": 0.7,
  "pending_sql": null,
  "cache_hit": false,
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "metadata": {
    "route": "rag",
    "retrieved_chunks": [...],
    "cache_hit": false,
    "reflection_iterations": 0,
    "reflection_score": null,
    "refined_question": null
  }
}
```

When SQL approval is pending, `answer` is empty and `pending_sql` is populated:

```json
{
  "answer": "",
  "sources": [],
  "confidence": 0.0,
  "pending_sql": {
    "sql": "SELECT * FROM k8s_events WHERE status = 'Error' LIMIT 10",
    "query_id": "550e8400-e29b-41d4-a716-446655440000",
    "explanation": "Fetches recent error events from the K8s events table"
  },
  "cache_hit": false,
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "metadata": {...}
}
```

### `TokenResponse` (from `/auth/register` and `/auth/login`)

```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

### `ServiceHealth` (from `/admin/health`)

```json
{
  "status": "ok",
  "qdrant": true,
  "postgres": true,
  "redis": true,
  "openai": true,
  "tavily": true
}
```

Status is `"degraded"` when any critical dependency (postgres, qdrant, openai) is down.

### `CacheStatsResponse` (from `/admin/cache/stats`)

```json
{
  "embedding": {"hits": 42, "misses": 8, "sets": 8, "hit_rate": 0.84},
  "rag": {"hits": 15, "misses": 5, "sets": 5, "hit_rate": 0.75},
  "sql_gen": {"hits": 3, "misses": 2, "sets": 2, "hit_rate": 0.6},
  "sql_result": {"hits": 1, "misses": 1, "sets": 1, "hit_rate": 0.5},
  "intent_router": {"hits": 30, "misses": 10, "sets": 10, "hit_rate": 0.75}
}
```

---

## HTTP Status Code Conventions

| Status | When |
|---|---|
| 200 | Successful query or SQL execution |
| 201 | User registration successful |
| 400 | Security scan blocked input |
| 401 | Missing / expired JWT |
| 403 | Authenticated but not admin |
| 409 | Username already exists |
| 422 | Request model validation failed |
| 429 | Rate limit or token budget exceeded |
| 500 | Unexpected server error |
| 502 | Upstream AI provider failed |
| 503 | Dependency (DB / Qdrant) unavailable |

---

## Headers

| Header | Direction | Description |
|---|---|---|
| `Authorization: Bearer <token>` | Request | JWT authentication |
| `X-Request-ID` | Both | Request correlation ID (generated if absent, echoed in response body) |
| `Content-Type: application/json` | Both | All request/response bodies are JSON |

---

## Validation

All request bodies are validated by Pydantic v2 before reaching handler code:
- String fields with `min_length` / `max_length` constraints
- Integer fields with `ge` / `le` bounds
- `Literal` enum fields for `search_mode`
- Custom `field_validator` for injection pattern checking on `question`
- Validation errors return `422` with `field_errors` list in `details`
