# TESTING_REPORT.md — VectraIQ Phase 5

**Date:** 2026-06-30

---

## Test Suite Overview

All tests live in `tests/`. No external services required — all I/O is mocked via `unittest.mock`.

| File | Coverage area | Tests |
|---|---|---|
| `tests/conftest.py` | Shared fixtures (TestClient, tokens, mocks) | — |
| `tests/test_auth.py` | Authentication endpoints | 13 |
| `tests/test_health.py` | Health + cache admin endpoints | 12 |
| `tests/test_query.py` | Query, streaming, SQL approval | 23 |
| `tests/test_models.py` | Pydantic model validation + injection prevention | 21 |
| `tests/test_security.py` | JWT helpers, password hashing, settings validation, error envelope | 16 |
| `tests/test_vector_store.py` | Sparse index caching (Phase 4 fix) | 7 |
| `tests/test_observability.py` | Timer, metrics dataclasses, record functions | 14 |

**Total:** ~106 test cases

---

## Running Tests

```bash
# All tests (offline, no credentials needed)
make test

# With coverage
pytest tests/ --cov=vectraiq --cov-report=term-missing

# Single file
pytest tests/test_auth.py -v

# Exclude slow tests (if any are marked)
pytest tests/ -m "not slow"
```

---

## Critical Path Coverage

### Authentication (`test_auth.py`)

| Test | Verified behavior |
|---|---|
| Register success | 201, valid JWT returned |
| Register duplicate | 409 with error envelope |
| Register short username/password | 422 validation error |
| Login success | 200, valid JWT with correct `sub` |
| Login wrong password | 401, generic message (no username enumeration) |
| Login unknown user | 401 |
| Protected endpoint without token | 403 |
| Protected endpoint with expired token | 401 |
| Admin endpoint with user token | 403 |

### Query Pipeline (`test_query.py`)

| Test | Verified behavior |
|---|---|
| RAG query success | 200, answer + sources + confidence |
| SQL interrupt | 200, `pending_sql` populated, empty `answer` |
| Cache hit flag | `cache_hit: true` in response |
| Empty question | 422 |
| Question > 2000 chars | 422 |
| Injection pattern (validator) | 422 |
| Invalid `search_mode` | 422 |
| `top_k` out of bounds | 422 |
| Rate limit exceeded | 429 |
| Token budget exceeded | 429 |
| LLM-Guard blocks input | 400 |
| Stream content-type | `text/event-stream` |
| Stream event order | `status` → ... → `result` → `done` |
| Stream includes `X-Request-ID` header | ✓ |
| SQL approve | 200, answer populated |
| SQL reject | 200, rejection message |

### Health & Admin (`test_health.py`)

| Test | Verified behavior |
|---|---|
| All healthy | 200, `status: ok` |
| Postgres down | 503, `status: degraded` |
| Qdrant down | 503 |
| Redis down (non-critical) | 200, `status: ok`, `redis: false` |
| Health shape | All 6 fields present |
| Health requires no auth | Not 401 / 403 |
| Cache stats requires admin | 403 for regular user |
| Cache stats shape | 5 tier keys, hit/miss/rate fields |
| Cache clear requires admin | 403 for regular user |
| Cache clear success | 200, `status: ok`, `cleared` list |

### Model Validation (`test_models.py`)

- 11 injection patterns tested via `@pytest.mark.parametrize`
- All field bounds tested (`top_k`, `confidence`, username/password lengths)
- `search_mode` enum validation
- `whitespace-only` and `punctuation-only` question rejection

### Security (`test_security.py`)

- bcrypt: wrong password fails, different hashes for same password, both verify
- JWT: correct claims, admin flag, expiry, wrong secret
- Pydantic settings validators: log_level, storage_backend, reranker_backend
- Error envelope: all 4xx responses include `{ error: { code, message }, request_id }`

### Sparse Index Cache (`test_vector_store.py`)

- First call builds index
- Subsequent calls within TTL reuse cached index (build called once)
- Call after TTL expiry triggers rebuild
- `invalidate_sparse_index()` forces rebuild on next call
- QdrantClient singleton returns same instance

---

## Mocking Strategy

### Why mock instead of integration tests?

The conftest uses `autouse=True` fixtures for rate limiter, token budget, and security pipeline passthrough. This keeps tests fast and offline while testing the endpoint logic correctly.

For full integration testing, override these fixtures and set `DATABASE_URL`/`QDRANT_URL` to real services.

### Mock layers

| External dep | Mock target | Fixture |
|---|---|---|
| PostgreSQL | `vectraiq.api.auth.psycopg2.connect` | `mock_db_*` fixtures |
| LangGraph | `vectraiq.api.query.graph` | `mock_graph_*` fixtures |
| Qdrant health | `vectraiq.api.admin._ping_qdrant` | `mock_all_healthy` etc. |
| Rate limiter | `vectraiq.api.query.is_allowed_user` | `bypass_rate_limiter` (autouse) |
| Token budget | `vectraiq.api.query.check_budget` | `bypass_token_budget` (autouse) |
| LLM-Guard | `vectraiq.api.query.check_input_safe` | `bypass_security_pipeline` (autouse) |

---

## Known Gaps

| Area | Status | Notes |
|---|---|---|
| CRAG / HyDE / Self-RAG unit tests | Not written | Would require mocking OpenAI calls in service layer |
| LangGraph node unit tests | Not written | Complex to mock PostgresSaver checkpointer |
| Frontend component tests | Not written | Need Jest + Testing Library setup |
| End-to-end tests (Playwright) | Not written | Need full stack running |
| `/documents/upload` endpoint | Not implemented | Backend endpoint missing; test pending |
| Reranker unit tests | Not written | Local CrossEncoder model required |

---

## CI Integration

Tests run automatically on every push to `main`/`master`/`develop` via `.github/workflows/ci.yml`:
- PostgreSQL 16 service container is provisioned for the test runner
- Coverage report uploaded to Codecov
- JUnit XML uploaded as artifact for PR annotations
