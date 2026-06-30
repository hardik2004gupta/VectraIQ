# OBSERVABILITY_GUIDE.md — VectraIQ Phase 5

**Date:** 2026-06-30

---

## Overview

VectraIQ has three observability layers, all opt-in via environment variables:

| Layer | Trigger | What it tracks |
|---|---|---|
| **Structured logging** | Always on | Request lifecycle, errors, security events |
| **Langfuse tracing** | `LANGFUSE_SECRET_KEY` + `LANGFUSE_PUBLIC_KEY` set | LLM calls, token usage, cost, trace trees |
| **OpenTelemetry** | `OTEL_EXPORTER_OTLP_ENDPOINT` set | Distributed traces (spans) to any OTLP backend |

---

## Structured Logging

### Configuration

```env
LOG_JSON=true       # JSON format for log aggregators (Datadog, CloudWatch, Loki)
LOG_LEVEL=INFO      # DEBUG | INFO | WARNING | ERROR | CRITICAL
```

In development (`LOG_JSON=false`), logs are human-readable with colors via loguru.  
In production (`LOG_JSON=true`), each log line is a single JSON object.

### Log Schema (JSON mode)

```json
{
  "timestamp": "2026-06-30T12:00:00.000Z",
  "level": "INFO",
  "message": "Query complete | rid=abc-123 user=alice intent=rag cache=false latency=1823.4ms",
  "function": "query_endpoint",
  "file": "vectraiq/api/query.py",
  "line": 160
}
```

### Key Log Events

| Event | Level | When |
|---|---|---|
| App startup | INFO | Server start |
| Config warnings | WARNING | Missing optional env vars |
| User authenticated | INFO | Successful login |
| User registered | INFO | New account created |
| Query complete | INFO | Full pipeline finished |
| SQL approval pending | INFO | LangGraph interrupted for SQL |
| SQL approved/rejected | INFO | SQL execution decision |
| Domain error | WARNING | Any VectraIQError raised |
| Unhandled exception | ERROR | Unexpected 500 |
| AI call | DEBUG | Every LLM/embedding call |
| Search | DEBUG | Every vector search call |
| Cache cleared | INFO | Admin cache clear |

### Request Tracing

Every request gets a UUID in `X-Request-ID` (injected by `RequestContextMiddleware`). This ID propagates through all log lines for that request, enabling correlation across the request lifecycle.

---

## Langfuse Tracing

### Setup

1. Create an account at [cloud.langfuse.com](https://cloud.langfuse.com) (free tier available)
2. Create a project and copy the keys
3. Set environment variables:

```env
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com   # or your self-hosted URL
LANGFUSE_ENABLED=true                       # set false to disable
```

4. Install the package (if not already present):
```bash
uv add langfuse
```

5. Restart the server. The startup log will confirm: `Langfuse tracing enabled`.

### What Gets Traced

| Event | Langfuse object | Fields |
|---|---|---|
| LLM call (generate/embed) | `generation` | model, prompt_tokens, completion_tokens, latency_ms, cache_hit |
| HTTP request | `trace` | request_id, endpoint, method, user_id, intent, latency_ms, status_code |

### Disabling Langfuse

Set either:
```env
LANGFUSE_ENABLED=false
```
or simply don't set `LANGFUSE_SECRET_KEY`/`LANGFUSE_PUBLIC_KEY`. The `_get_langfuse()` function returns `None` and all `record_*` functions fall through to log-only mode. No overhead is added when disabled.

### Langfuse Dashboard

Once connected, the Langfuse dashboard provides:
- **Traces:** Full request timeline with nested LLM generation spans
- **Generations:** All LLM calls with token counts and latency
- **Cost tracking:** Estimated USD cost per call (based on model pricing)
- **User sessions:** Group traces by `user_id` to see per-user usage
- **Latency analytics:** P50/P95/P99 breakdowns by endpoint

---

## OpenTelemetry

### Setup

Set:
```env
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
OTEL_ENABLED=true
```

Compatible backends: Jaeger, Tempo, Honeycomb, Datadog, Dynatrace, New Relic.

### Current Status

OTel hook points exist in `vectraiq/observability.py` as `_OTEL_ENABLED` flag. The hook functions (`record_ai_call`, `record_search`, `record_request`) check this flag but the OTel SDK calls are not yet wired. To add OTel spans:

```python
# In record_ai_call():
if _OTEL_ENABLED:
    from opentelemetry import trace
    tracer = trace.get_tracer("vectraiq")
    with tracer.start_as_current_span(f"ai.{metrics.operation}") as span:
        span.set_attribute("model", metrics.model)
        span.set_attribute("tokens.total", metrics.total_tokens)
```

This is intentionally deferred — wiring full OTel instrumentation requires adding `opentelemetry-sdk` and `opentelemetry-exporter-otlp` to `pyproject.toml`.

---

## Observability Extension Points

The `observability.py` module is designed so that `record_ai_call`, `record_search`, and `record_request` are the only functions that need to change to add any monitoring backend. Call sites use these functions and context managers — they don't import Langfuse or OTel directly.

```
vectraiq/
  observability.py          ← change here to add new backends
  ai/
    llm_service.py          → calls record_ai_call via timed_ai_call
    vector_store.py         → calls record_search via timed_search
  api/
    query.py                → calls timer() for request latency
    admin.py                → (future) calls record_request
```

---

## Alerting Recommendations

| Signal | Recommended alert | Threshold |
|---|---|---|
| `GET /admin/health` → 503 | PagerDuty / Slack | Any 503 |
| Error rate | Loki / CloudWatch | >5% of `/query` requests return 5xx |
| P95 latency | Grafana | >8s on `/query` |
| Token budget exhaustion | Langfuse | `budget/exceeded` errors > 10/hour |
| Rate limit hits | Log filter | `rate_limit_exceeded` > 50/hour per user |
