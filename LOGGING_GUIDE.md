# LOGGING_GUIDE.md — VectraIQ Phase 3

## Configuration

Logging is configured once at app startup in the `lifespan()` function in `main.py`:

```python
configure_logging(log_level=settings.log_level, log_json=settings.log_json)
```

| Env var | Default | Description |
|---|---|---|
| `LOG_LEVEL` | `INFO` | Minimum log level: DEBUG \| INFO \| WARNING \| ERROR \| CRITICAL |
| `LOG_JSON` | `false` | Set `true` in production for structured JSON lines |

---

## Log Formats

### Development (LOG_JSON=false)

```
2026-06-30 14:32:11.042 | INFO     | vectraiq.api.query:query_endpoint:67 | rid=550e8400 — Query complete | rid=550e8400 user=agent@demo.local intent=rag cache=False latency=312.4ms
```

### Production (LOG_JSON=true)

```json
{"ts": "2026-06-30T14:32:11.042+00:00", "level": "INFO", "logger": "vectraiq.api.query", "request_id": "550e8400-e29b-41d4-a716-446655440000", "message": "Query complete | rid=550e8400 user=agent@demo.local intent=rag cache=False latency=312.4ms"}
```

---

## Request Correlation

Every request receives a unique `request_id` (UUID4). It is:
- Generated in `RequestContextMiddleware` (or inherited from `X-Request-ID` header)
- Stored in a `contextvars.ContextVar` accessible anywhere via `get_request_id()`
- Automatically included in **every** log line via loguru patcher
- Returned to callers in the `ChatResponse.request_id` field and error envelopes

To correlate all log lines for a single request:
```bash
grep "550e8400" app.log
```

---

## Log Events Reference

### Access log (one per request, from `RequestContextMiddleware`)

```
Access | rid=<id> method=POST path=/query status=200 latency=312.4ms client=10.0.0.5
```

Level: INFO (200-399), WARNING (400-499), ERROR (500+)

### Query complete (from `api/query.py`)

```
Query complete | rid=<id> user=agent@demo.local intent=rag cache=False latency=312.4ms
```

### SQL approval pending

```
SQL approval pending | rid=<id> user=agent@demo.local thread=<thread_id> latency=87.2ms
```

### SQL approved/rejected

```
SQL approved | rid=<id> user=admin@demo.local thread=<thread_id> latency=42.1ms
SQL rejected | rid=<id> user=admin@demo.local thread=<thread_id> latency=3.2ms
```

### CRAG outcome (from `ai/rag_service.py`)

```
CRAG | enabled=True score=0.82 label=relevant used_web=False
```

### AI call timing (DEBUG, from `observability.py`)

```
AI call | provider=openai model=gpt-4o op=generate tokens=1842 latency=1243.7ms cache=False
```

### Security events

```
Domain error | rid=<id> type=InjectionDetectedError message=Input blocked by PromptInjection
Domain error | rid=<id> type=RateLimitError message=Rate limit exceeded. Please retry later.
```

### User auth events

```
User registered | username=sre-operator
User authenticated | username=sre-operator
```

### Cache cleared

```
Cache cleared by admin | user=admin@demo.local cleared=['memory (47 entries)']
```

### Degradation warnings

```
Redis unavailable for rate limiting; allowing request
Redis unavailable for token budget check; allowing request
Config missing: OPENAI_API_KEY
Config missing: JWT_SECRET
```

---

## Stdlib Bridge

All third-party logging (uvicorn, fastapi, httpx, qdrant-client, openai) is routed through loguru via `_StdlibHandler`. This means a single `LOG_LEVEL` controls everything and all log lines appear in the same format.

---

## Adding Log Statements

Always use loguru's lazy format strings (not f-strings in the log call):

```python
from loguru import logger

# Good — loguru evaluates lazily only if level is active
logger.info("Query complete | user={} latency={:.1f}ms", user.username, elapsed_ms)

# Bad — f-string evaluated even if DEBUG is filtered
logger.debug(f"Retrieved {len(chunks)} chunks")  # noqa

# Good
logger.debug("Retrieved {} chunks", len(chunks))
```

Use `logger.exception()` (not `logger.error()`) when inside an `except` block to capture the traceback:

```python
try:
    rows = sql_service.execute_sql(sql)
except Exception:
    logger.exception("SQL execution failed for query_id={}", query_id)
```

---

## Future: Langfuse / OTEL Integration

To push AI call metrics to an external provider, replace the body of `record_ai_call()` in `vectraiq/observability.py`:

```python
def record_ai_call(metrics: AICallMetrics) -> None:
    # Replace with:
    langfuse.generation(
        name=metrics.operation,
        model=metrics.model,
        usage={"promptTokens": metrics.prompt_tokens, "completionTokens": metrics.completion_tokens},
        latency=metrics.latency_ms / 1000,
    )
```

No call sites need to change — `timed_ai_call()` is already wrapping every LLM call.
