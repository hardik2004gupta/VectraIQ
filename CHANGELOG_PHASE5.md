# CHANGELOG_PHASE5.md — VectraIQ Phase 5

**Date:** 2026-06-30  
**Branch:** master  
**Scope:** Production hardening — testing, observability, security, CI/CD, documentation, GitHub polish

---

## Part 1 — Comprehensive Testing

### T-001 · Test infrastructure scaffolded

**Files added:**
- `tests/__init__.py`
- `tests/conftest.py`

`conftest.py` provides a session-scoped `TestClient`, JWT token fixtures for user and admin, Postgres mocks (user exists / empty / register ok / duplicate), LangGraph graph mocks (RAG result, SQL interrupt, SQL result), and `autouse` fixtures that bypass rate limiting, token budget, and the LLM-Guard security pipeline so tests run offline without credentials.

### T-002 · Authentication tests

**File:** `tests/test_auth.py` (13 tests)

Covers: register success + JWT validity, duplicate username 409, field length validation 422, login success + JWT claims, wrong password 401, unknown user 401, generic error message (no username enumeration), expired token 401, invalid token 401, admin-only endpoint with user token 403.

### T-003 · Health and admin endpoint tests

**File:** `tests/test_health.py` (12 tests)

Covers: all-healthy 200, Postgres-down 503, Qdrant-down 503, Redis-down non-critical (still 200), response shape, no-auth-required on health, cache stats admin-only, cache stats response shape, cache clear admin-only, cache clear success.

### T-004 · Query endpoint tests

**File:** `tests/test_query.py` (23 tests)

Covers: RAG success, SQL interrupt (pending_sql populated), cache hit flag, empty question 422, oversized question 422, injection pattern 422, invalid search_mode 422, top_k bounds 422, rate limit 429, token budget 429, LLM-Guard rejection 400. SSE: content-type, event order (status→result→done), X-Request-ID header. SQL execute: approve, reject, no-auth 403, missing fields 422.

### T-005 · Model validation tests

**File:** `tests/test_models.py` (21 tests)

Covers: all 11 injection patterns parametrized, field bounds (top_k, confidence, username/password length), search_mode enum, whitespace-only rejection, punctuation-only rejection, special characters allowed in K8s queries.

### T-006 · Security utility tests

**File:** `tests/test_security.py` (16 tests)

Covers: bcrypt hash not plaintext, correct password verifies, wrong password fails, different salts for same password, JWT claims, admin flag, expiry, wrong secret. Pydantic Settings validators: log_level, storage_backend, reranker_backend. Error envelope shape on all 4xx responses.

### T-007 · Sparse index cache tests

**File:** `tests/test_vector_store.py` (7 tests)

Covers: first call builds index, reuse within TTL (build called once), rebuild after TTL expiry, `invalidate_sparse_index()` forces rebuild, built_at reset on invalidation, QdrantClient singleton.

### T-008 · Observability module tests

**File:** `tests/test_observability.py` (14 tests)

Covers: timer elapsed increases, is float, accumulates. `timed_ai_call` populates latency/provider/model, captures error string, re-raises exception. `timed_search` populates latency and mode, yields mutable metrics. All dataclass defaults. `record_*` functions don't raise.

---

## Part 2 — Performance

No code changes in Part 2. See `PERFORMANCE_REPORT.md` for latency analysis, caching impact, and optimization recommendations. The Phase 4 sparse index caching fix (TD-007) is the primary performance improvement for this version.

---

## Part 3 — Observability

### O-001 · Langfuse integration added

**File:** `vectraiq/observability.py`

Added `_LANGFUSE_ENABLED` feature flag that activates when `LANGFUSE_SECRET_KEY` and `LANGFUSE_PUBLIC_KEY` are set. Lazy-initializes `Langfuse` client on first use. `record_ai_call()` now optionally sends `generation` events to Langfuse. `record_request()` now optionally sends `trace` events.

Disabling: set `LANGFUSE_ENABLED=false` or leave keys unset. No overhead when disabled.

### O-002 · OpenTelemetry hooks documented

**File:** `vectraiq/observability.py`

`_OTEL_ENABLED` flag added. Extension points documented for wiring OTel spans in `record_ai_call`. Full OTel SDK integration deferred pending `opentelemetry-sdk` dependency addition.

### O-003 · Langfuse and OTEL settings added to config

**File:** `vectraiq/config.py`

Added `langfuse_secret_key`, `langfuse_public_key`, `langfuse_host`, `langfuse_enabled`, `otel_exporter_otlp_endpoint`, `otel_enabled` settings — all with safe defaults (disabled / empty string).

---

## Part 4 — Security Hardening

### SH-001 · Security headers middleware

**File:** `vectraiq/middleware/security_headers.py` (new)  
**Registered in:** `vectraiq/main.py`

All responses now include `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, and `Content-Security-Policy` headers. The `Server` header from uvicorn is stripped.

Addresses OWASP A05 Security Misconfiguration.

---

## Part 5 — CI/CD

### CI-001 · GitHub Actions CI pipeline

**File:** `.github/workflows/ci.yml`

Jobs: `backend-lint` (ruff), `backend-typecheck` (mypy, advisory), `backend-tests` (pytest + PostgreSQL service container + Codecov upload), `frontend-lint` (tsc + next lint), `frontend-build` (next build), `docker-build` (no push, GHA cache), `security-scan` (pip-audit + npm audit, advisory), `ci-gate` (summary job for branch protection).

Concurrency group cancels in-progress runs on new push to same branch.

### CI-002 · GitHub Actions release pipeline

**File:** `.github/workflows/release.yml`

Triggered by `v*.*.*` tags. Builds and pushes Docker image to GHCR with semver tags. Creates GitHub Release with auto-generated release notes.

---

## Part 6 — Documentation

### D-001 · README complete rewrite

**File:** `README.md`

Professional README with: CI/license/tech badges, feature table, ASCII architecture diagram, Mermaid flowchart, quick start (Docker + local), environment variable reference, API endpoint table, test instructions, project structure, deployment section, evaluation section, roadmap, contributing/security/license links.

### D-002 · CONTRIBUTING.md

**File:** `CONTRIBUTING.md`

Covers: prerequisites, setup, dev workflow, test commands, code style (backend + frontend), PR process, branch conventions, commit message format, what is and isn't accepted.

---

## Part 7 — GitHub Polish

### G-001 · Issue templates

**Files:**
- `.github/ISSUE_TEMPLATE/bug_report.md` — structured bug report with environment, reproduction steps, logs
- `.github/ISSUE_TEMPLATE/feature_request.md` — problem statement, proposed solution, acceptance criteria

### G-002 · PR template

**File:** `.github/PULL_REQUEST_TEMPLATE.md`

Includes summary, changes section, test plan checklist, general checklist (no secrets, Pydantic models updated, CHANGELOG updated).

### G-003 · SECURITY.md

**File:** `SECURITY.md`

Supported versions table, vulnerability reporting contact (email, 48h SLA), full 10-layer security architecture, known limitations, security headers list, CI dependency audit process.

### G-004 · LICENSE

**File:** `LICENSE` — MIT License, 2026.

---

## Known Open Issues

| ID | Severity | Description |
|---|---|---|
| KB-001 | Medium | `/documents/upload` backend endpoint not implemented |
| SEC-001 | Medium | SQL approval not user-scoped |
| CACHE-001 | Low | Redis `cache.clear()` no-op for remote entries |
| AUTH-001 | Low | No refresh token flow |
| OTEL-001 | Low | OTel SDK not wired despite feature flag existing |
