# ERROR_HANDLING_GUIDE.md — VectraIQ Phase 3

## Architecture

Error handling is centralized in `vectraiq/main.py` via FastAPI exception handlers. Business logic raises typed domain exceptions; handlers convert them to HTTP responses. No `try/except` blocks in business logic for HTTP concerns.

```
Handler code             Domain exceptions           HTTP response
─────────────────────────────────────────────────────────────────
api/auth.py         → raises ConflictError       → 409 ErrorResponse
api/query.py        → raises RateLimitError       → 429 ErrorResponse
middleware/auth.py  → raises TokenExpiredError    → 401 ErrorResponse
                    → raises AuthorizationError   → 403 ErrorResponse
                         ↓
             main.py exception handlers
                         ↓
             ErrorResponse JSON (always same shape)
```

---

## Exception Hierarchy (`vectraiq/exceptions.py`)

```
VectraIQError                      (base, 500)
├── AuthenticationError            (401)
│   └── TokenExpiredError          (401)
├── AuthorizationError             (403)
├── RateLimitError                 (429)
├── TokenBudgetError               (429)
├── InputValidationError           (400)
│   ├── InjectionDetectedError     (400)
│   └── ContentBlockedError        (400)
├── AIProviderError                (502)
│   └── EmbeddingError             (502)
├── VectorStoreError               (503)
├── DatabaseError                  (503)
│   └── SQLExecutionError          (503)
├── SQLGenerationError             (422)
├── CacheError                     (503, non-fatal)
├── WebSearchError                 (502)
├── NotFoundError                  (404)
└── ConflictError                  (409)
```

Each exception carries:
- `http_status` — the HTTP status code to return
- `error_code` — the machine-readable string in the error envelope
- `message` — human-readable description

---

## Registered Exception Handlers

### 1. `VectraIQError` → `_vectraiq_error_handler`

Catches all domain exceptions. Uses `exc.http_status` and `exc.error_code` automatically.

```python
async def _vectraiq_error_handler(request, exc: VectraIQError) -> JSONResponse:
    return _error_response(
        code=exc.error_code,
        message=exc.message,
        http_status=exc.http_status,
    )
```

### 2. `HTTPException` → `_http_exception_handler`

Wraps FastAPI's native `HTTPException` in the standard error envelope (e.g. `405 Method Not Allowed` from routing).

### 3. `RequestValidationError` → `_validation_error_handler`

Converts Pydantic v2 validation errors to `422` with human-readable `field_errors` list.

Example response:
```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed",
    "details": {
      "field_errors": [
        "body → question: ensure this value has at most 2000 characters"
      ]
    }
  },
  "request_id": "..."
}
```

### 4. `Exception` → `_generic_error_handler`

Last-resort catch-all. Logs the full traceback, returns generic `500`. Does NOT leak internal details to the caller.

---

## How to Raise Errors in Application Code

**Do:**
```python
from vectraiq.exceptions import RateLimitError, AuthenticationError

# In a route handler or service function
if not allowed:
    raise RateLimitError()

if not verified:
    raise AuthenticationError("Invalid username or password")
```

**Don't:**
```python
from fastapi import HTTPException

# Avoid — bypasses domain exception hierarchy
raise HTTPException(status_code=429, detail="Rate limit exceeded")
```

---

## Adding a New Exception

1. Add a class to `vectraiq/exceptions.py`:

```python
class DocumentNotFoundError(NotFoundError):
    error_code = "document_not_found"

    def __init__(self, doc_id: str) -> None:
        super().__init__(f"Document '{doc_id}' not found")
        self.doc_id = doc_id
```

2. Raise it in business logic — the global handler does the rest.

No handler registration needed for `VectraIQError` subclasses.

---

## Error Handling in AI Services

AI services (RAG, SQL, CRAG, etc.) handle their own internal errors gracefully and return degraded results rather than raising. This is intentional — these services are designed to be resilient:

```python
# In crag.py — CRAG failure falls through to rag-only
except Exception:
    logger.exception("CRAG grading failed; using original chunks")
    return chunks, CRAGEvaluation(), False
```

Only unrecoverable or security-relevant errors propagate up to the API layer.

---

## Security Error Strategy

Security-related errors are deliberately opaque on login:

```python
# auth.py — doesn't reveal whether username exists
if row is None or not verify_password(body.password, row[0]):
    raise AuthenticationError("Invalid username or password")
```

For injection/moderation blocks, the reason IS included to help clients fix their input:

```python
raise InjectionDetectedError(guard_reason)  # e.g. "Input blocked by PromptInjection"
raise ContentBlockedError(mod_reason)        # e.g. "Content blocked by Toxicity"
```
