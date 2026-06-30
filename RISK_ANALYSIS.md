# VectraIQ v2 — Risk Analysis
**Version:** 2.0  
**Status:** Design Phase  

---

## Risk Summary Matrix

| Risk | Phase | Probability | Impact | Severity | Mitigation |
|---|---|---|---|---|---|
| Dual path divergence during transition | 3 | High | High | **Critical** | Feature flag + parallel test |
| psycopg2 → v3 connection failure | 2 | Medium | High | **High** | Separate PR, integration test first |
| Sparse index singleton memory pressure | 2 | Medium | Medium | **Medium** | Memory limit + eviction |
| LangGraph checkpoint schema mismatch | 4 | Medium | High | **High** | Version collection name |
| Reranker cold start on Railway restart | 6 | High | Low | **Medium** | Startup warmup ping |
| SQL injection through improved validator | 2 | Low | Critical | **High** | Adversarial test suite |
| JWT_SECRET rotation invalidates sessions | 6 | Low | Medium | **Medium** | Document rotation runbook |
| Qdrant Cloud costs exceed budget | 6 | Medium | Medium | **Medium** | Set vector count alert |
| Railway cold start (Hobby tier) | 6 | High | Medium | **High** | Upgrade to Standard or use health check warmup |
| Streamlit → Next.js feature parity gap | 5 | Medium | Low | **Low** | Keep streamlit until e2e passes |
| Vanna removal breaks hidden path | 3 | Low | Low | **Low** | Grep for all Vanna imports before removal |

---

## Risk 1 — Dual Execution Path Divergence (CRITICAL)

**Phase:** 3 (Clean Architecture)

**Description:** During Phase 3, both `rag_service.py` (inline paths) and `graph.py` (LangGraph paths) will coexist temporarily. If a bug fix is applied to one but not the other, the two paths will return different results for the same query. Since the router determines which path runs, this is silent divergence — no error is raised, users just get inconsistent answers.

**Probability:** High. The v1 codebase already has this problem and is the primary motivation for ADR-002.

**Impact:** Users report inconsistent answers. Debugging is extremely difficult because the code path is non-deterministic from the user's perspective.

**Mitigation:**
1. In Phase 3 Step 3.3, immediately remove `_run_sql_inline` and `_run_hybrid_inline` from `rag_service.py` as the FIRST refactoring step (not the last).
2. After removal, run the full test suite on every commit.
3. Do not run Phase 3 for more than 1 week — the window where dual paths coexist must be short.
4. Add a CI check: `grep -r "_run_sql_inline\|_run_hybrid_inline" apps/` must return empty.

**Rollback:** If Phase 3 breaks production, revert the branch entirely. Phase 2 fixes are independent and do not depend on Phase 3 structure.

---

## Risk 2 — psycopg2 → v3 Migration Failures

**Phase:** 2 (Critical Bug Fixes, Fix 2.10)

**Description:** `app/api/auth.py` uses psycopg2. `app/core/graph.py` uses psycopg v3. Migrating auth.py to v3 requires:
- Different connection string format (`postgresql+psycopg://` vs `postgresql://`)
- Different cursor behavior (v3 cursors are not drop-in replacements)
- Different parameter placeholder syntax (v3 uses `%s` but with different binary handling)

**Probability:** Medium. The APIs are similar but not identical.

**Impact:** Auth endpoint breaks → all users are logged out → total service disruption.

**Mitigation:**
1. Fix 2.10 must be a dedicated PR with NO other changes.
2. Write integration test for login + token validation BEFORE migrating.
3. Migrate auth.py in a dev branch and run the test against a local Postgres before merging.
4. Test both connection pooling (psycopg AsyncConnectionPool) and single connection modes.
5. Keep psycopg2 in pyproject.toml as a fallback during Phase 2. Remove it in Phase 3.

**Rollback:** Revert Fix 2.10 PR. Auth reverts to psycopg2. All other fixes remain.

---

## Risk 3 — Sparse Index Singleton Memory Pressure

**Phase:** 2 (Critical Bug Fix 2.3)

**Description:** The TF-IDF sparse index built from 10,000 Qdrant documents will be held in memory permanently as a singleton. On Railway Hobby tier (512 MB), a TF-IDF matrix for 10K documents × N vocabulary terms can reach 100–300 MB, leaving little room for the CrossEncoder model (~350 MB) and the application itself.

**Probability:** Medium on Hobby tier. Low on Standard tier.

**Impact:** Railway OOM kill → container restart → cold start of all singletons → slow first query.

**Mitigation:**
1. Add `max_docs` parameter to sparse index build: cap at 5,000 documents initially.
2. Use scipy sparse matrix format (already default in scikit-learn TfidfVectorizer) — 10–30x more memory efficient than dense.
3. Upgrade Railway to Standard (1 GB) for production.
4. Add memory usage logging at startup: log sparse index size after build.
5. Set Railway memory alert at 80% to get warning before OOM.

**Rollback:** If OOM occurs, set `SPARSE_MAX_DOCS=1000` environment variable and restart. Reduces accuracy but prevents crash.

---

## Risk 4 — LangGraph Checkpoint Schema Mismatch

**Phase:** 4 (AI Improvements — LangGraph v2 Graph)

**Description:** The v1 graph uses a `GraphState` TypedDict with 22 fields. The v2 graph uses 20 fields with different names (e.g., `raw_answer` → `answer`). LangGraph stores state in Postgres as JSON. If old checkpoint records exist when v2 graph starts, `checkpoint.state` will have missing fields or wrong types, causing `KeyError` or `ValidationError` on resume.

**Probability:** Medium. Only affects users with in-progress SQL approval threads from v1.

**Impact:** In-flight SQL approval threads become un-resumable. Users see 500 error when trying to approve SQL.

**Mitigation:**
1. Rename the LangGraph collection/table for v2: use `vectraiq_v2_checkpoints` instead of the v1 table name.
2. Migration script: `SELECT * FROM checkpoints WHERE created_at < '2026-XX-XX'` — archive old rows, don't carry forward.
3. Add `try/except` around checkpoint resume with fallback to restarting the query from scratch.
4. Announce to users: "in-progress SQL approvals will need to be re-submitted during the upgrade."

**Rollback:** Point `CHECKPOINT_TABLE=vectraiq_v1_checkpoints` env var to revert to v1 table.

---

## Risk 5 — Railway Cold Start Latency

**Phase:** 6 (Production Hardening)

**Description:** Railway Hobby tier spins down containers after 30 minutes of inactivity. When the next request arrives, the container restarts from scratch, triggering:
- CrossEncoder model load (~3s)
- Sparse index build from 10K Qdrant docs (~5s)
- SQL schema inspection (~1s)
- Total cold start: ~10–15s before first query can be answered

**Probability:** High on Hobby tier.

**Impact:** First request after idle takes 10–15 seconds. User sees a timeout or very slow response.

**Mitigation:**
1. Upgrade to Railway Standard tier (containers stay warm).
2. If staying on Hobby: deploy a simple cron job (GitHub Actions scheduled workflow) that pings `/api/v1/health` every 25 minutes to prevent idle shutdown.
3. Add startup time logging: log time taken for each singleton initialization at DEBUG level.
4. Frontend: show "Warming up..." message if request takes >5 seconds, with a friendly explanation.

---

## Risk 6 — SQL Injection via Improved Validator Edge Cases

**Phase:** 2 (Critical Bug Fix 2.9)

**Description:** The improved `is_select_only()` validator handles semicolon injection and comment stripping, but SQL injection techniques evolve. Edge cases include: Unicode lookalike semicolons, MySQL `\` escaping, stored procedure calls via SELECT, and CTEs with DML (`WITH x AS (DELETE FROM ...) SELECT * FROM x`).

**Probability:** Low for the K8s SRE use case (internal users). Higher if API is ever public-facing.

**Impact:** Data destruction or exfiltration via the SQL execution endpoint.

**Mitigation:**
1. Write a minimum of 25 adversarial test cases for `is_select_only()` covering known bypass techniques.
2. Use `sqlglot.parse()` for AST-level validation rather than regex — AST cannot be fooled by string tricks.
3. SQL execution only runs after explicit human-in-the-loop approval via LangGraph interrupt.
4. SQL runs as a Postgres role with READ ONLY privileges only (`GRANT SELECT ON ALL TABLES`). Even if a DML query bypasses the validator, Postgres will reject it at the database level.
5. Log every SQL query executed (with user_id, timestamp) to a tamper-evident audit table.

**Rollback:** If a vulnerability is discovered, set `SQL_EXECUTION_ENABLED=false` in env vars and restart. Disables the entire Text2SQL feature instantly.

---

## Risk 7 — JWT_SECRET Rotation Breaks All Sessions

**Phase:** 6 (Production Hardening)

**Description:** Rotating the `JWT_SECRET` (e.g., for security hygiene or after a suspected leak) immediately invalidates all existing JWT tokens. All logged-in users are signed out simultaneously.

**Probability:** Low (rotation is infrequent but planned).

**Impact:** All users must log in again. For an SRE tool used during incidents, this is disruptive.

**Mitigation:**
1. Document the rotation runbook in `docs/operations.md`.
2. For planned rotation: announce 24 hours in advance.
3. Future enhancement (Phase 7+): support two active JWT secrets simultaneously with a grace period (`JWT_SECRET_PREVIOUS` env var) to allow gradual rotation.
4. Set JWT expiry to 24 hours (already planned) — even without rotation, tokens expire naturally.

---

## Risk 8 — Qdrant Cloud Cost Overrun

**Phase:** 6 (Production Hardening)

**Description:** Qdrant Cloud free tier allows ~1M vectors. `text-embedding-3-large` produces 3072-dimensional vectors. Each document chunk becomes one vector. At 100 chunks per document, 10,000 documents = 1M vectors, hitting the free tier limit.

**Probability:** Medium for active knowledge bases.

**Impact:** Qdrant rejects new document uploads. Users can query but cannot add documents.

**Mitigation:**
1. Set monitoring alert at 800K vectors (80% of free tier).
2. Implement vector count check in the admin health dashboard.
3. Offer `--dimensions 1536` option: use `text-embedding-3-small` for less critical document types.
4. Budget plan: Qdrant Starter ($25/month) supports 10M vectors — upgrade before hitting limit.

---

## Risk 9 — Vanna Removal Breaks Hidden Import

**Phase:** 3 (Clean Architecture, Step 3.6)

**Description:** Vanna is in `pyproject.toml` but not used in `sql_service.py`. However, it might be imported somewhere less obvious (config.py, __init__.py, a dev script) that wasn't caught in the audit.

**Probability:** Low. Audit found no Vanna usage beyond the dependency declaration.

**Impact:** Import error after Vanna removal → API fails to start.

**Mitigation:**
1. Before removing: `grep -r "vanna\|Vanna" apps/ scripts/ --include="*.py"` — verify zero results.
2. Remove from pyproject.toml in a separate commit from any other changes.
3. Run `python -c "from apps.api.src.main import app"` immediately after removal to verify startup.

---

## Risk 10 — llm-guard Silent Failure (Security Risk)

**Phase:** Active in all phases

**Description:** `input_guard.py` has graceful degradation: if llm-guard fails (model download issue, OOM, exception), it logs a warning and allows the request through. This means a misconfigured or broken llm-guard silently stops scanning inputs.

**Probability:** Medium — llm-guard model downloads can fail on first startup.

**Impact:** Prompt injection, PII leakage, or jailbreak attempts reach the LLM without scanning.

**Mitigation:**
1. At startup pre-flight: attempt a test scan with a benign string. If it fails, log a CRITICAL-level error (not just warning).
2. Add `LLM_GUARD_REQUIRED=true` env var: if set, startup fails when llm-guard cannot initialize instead of continuing.
3. Default `LLM_GUARD_REQUIRED=false` in development (allows faster local iteration), `true` in production.
4. Add `/api/v1/health` check: include `llm_guard: "ok" | "degraded"` in response.

---

## General Rollback Strategy

### Per-Phase Rollback

Each phase is on a separate git branch. Rolling back means:
1. Revert to the previous phase's branch on Railway.
2. The database schema at each phase boundary is documented in `seed/migrations/`.
3. Never apply a migration that cannot be reversed (add `-- ROLLBACK:` comment with reverse SQL).

### Feature Flag Killswitches

| Feature | Env Var | Safe Default |
|---|---|---|
| SQL execution | `SQL_EXECUTION_ENABLED=false` | Disables Text2SQL entirely |
| llm-guard | `LLM_GUARD_ENABLED=false` | Skip scanning (lower security) |
| CRAG web search | `CRAG_ENABLED=false` | Use local results only |
| Self-RAG | `SELF_RAG_ENABLED=false` | Single-pass generation |
| HyDE | `HYDE_ENABLED=false` | Standard retrieval |
| Sparse search | `HYBRID_ENABLED=false` | Dense-only retrieval |

All features can be disabled without code changes, only environment variable changes and a container restart (~5 seconds).

### Emergency Contacts (Operational)

For a production incident during migration:
1. Check Railway logs first: `railway logs --service api`
2. Check `/api/v1/health` — identifies which service is down
3. If database issue: Neon console → check connection count and active queries
4. If Qdrant issue: Qdrant Cloud console → check cluster status
5. If Redis issue: Upstash console → check command rate
