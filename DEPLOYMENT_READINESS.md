# DEPLOYMENT_READINESS.md — VectraIQ v1.0

**Date:** 2026-06-30  
**Target environments:** Docker Compose (self-hosted), Railway (backend), Vercel (frontend)

---

## 1. Docker Compose (Self-Hosted)

### Current `docker-compose.yml` review

**Strengths:**
- `postgres:16` with `pg_isready` healthcheck — app waits for DB to be ready
- `qdrant:v1.17.0` pinned version — reproducible builds
- App `depends_on` with `condition: service_healthy` — correct startup order
- App healthcheck: `curl -f http://localhost:8000/admin/health` — appropriate
- Volume mounts for Postgres and Qdrant data persistence
- Environment variables use `${VAR:-default}` fallback syntax

**Gaps:**

| Issue | Risk | Impact |
|---|---|---|
| No `restart: unless-stopped` on any service | High | Containers will not restart after crashes or server reboots |
| Container runs as root (Dockerfile) | Medium | Security risk in shared environments |
| No `.dockerignore` | Medium | Build context includes `.git/`, `frontend/`, `notebooks/` etc. — slow builds, potential secrets leak |
| No resource limits (`mem_limit`, `cpus`) | Low | Runaway OOM could bring down host |
| `psycopg[binary]` installed twice (Dockerfile + pyproject.toml) | Low | Harmless redundancy after Phase 4 fix |

**Production docker-compose.yml — required additions before any deployment:**
```yaml
# Add to each service:
restart: unless-stopped

# Add to app service:
deploy:
  resources:
    limits:
      memory: 4G
      cpus: '2'
```

### Dockerfile review

```dockerfile
FROM python:3.12-slim       ✅ Appropriate base
WORKDIR /app                ✅
RUN pip install uv          ✅
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen        ✅ Locked deps
COPY vectraiq/ ./vectraiq/  ✅ Phase 4 fix
EXPOSE 8000                 ✅
CMD ["python", "scripts/serve.py"]  ✅
```

**Critical missing:**
```dockerfile
# Missing in current Dockerfile:
RUN useradd -m appuser
USER appuser
```

Without this, the container process runs as root (UID 0). If the container is compromised, the attacker has root access to the container filesystem.

**Also missing:** `.dockerignore` in repository root. Current Docker build context will include:
- `.git/` directory (can expose git history including any accidentally committed secrets)
- `frontend/node_modules/` (large, unnecessary)
- `notebooks/` (not needed in production image)
- `eval/` (not needed in production image)

**Estimated current image size:** ~3–4GB (PyTorch CPU + sentence-transformers + all deps)

---

## 2. Railway (Backend)

### Deployment readiness

Railway auto-detects Python projects via `pyproject.toml`. The `Procfile` or start command needs to be set.

**Start command:** `python scripts/serve.py`  
`scripts/serve.py` wraps uvicorn with `host=0.0.0.0` and `port=int(os.environ.get("PORT", 8000))` — Railway injects `PORT` automatically. ✅

**Required Railway environment variables:**
```
OPENAI_API_KEY=sk-...
JWT_SECRET=<strong-random-secret>
DATABASE_URL=postgresql://...   # Railway Postgres service
QDRANT_URL=https://...          # Railway Qdrant addon or Qdrant Cloud
UPSTASH_REDIS_URL=https://...   # Upstash or Railway Redis
UPSTASH_REDIS_TOKEN=...
FRONTEND_ORIGINS=https://your-app.vercel.app
LOG_JSON=true
LOG_LEVEL=WARNING
LANGFUSE_SECRET_KEY=...         # Optional
LANGFUSE_PUBLIC_KEY=...         # Optional
```

**Railway-specific concerns:**
- Railway uses ephemeral storage — `STORAGE_BACKEND` must be `s3` (not `local`) for any file persistence
- Railway provides PostgreSQL as an add-on — `DATABASE_URL` will be injected
- LangGraph PostgresSaver will attempt to create `checkpoints` table on startup — Railway Postgres allows DDL ✅
- The seed K8s documents must be ingested via `make seed` after initial deployment — Railway doesn't auto-run this

**Railway readiness: 7/10** — Works with correct env vars; `local` storage won't persist.

---

## 3. Vercel (Frontend)

### Deployment readiness

Next.js 15 App Router is first-class on Vercel. The frontend is well-suited for Vercel deployment.

**Required configuration:**
- Root directory: `frontend`
- Framework: Next.js (auto-detected from `next.config.ts`)
- Environment variable: `NEXT_PUBLIC_API_URL=https://your-api.railway.app`

**`next.config.ts` review (inferred from architecture):**

The frontend uses `NEXT_PUBLIC_API_URL` as the API base URL. This is correctly named for public env var exposure in Next.js.

**SSE streaming concern:**
Vercel Functions have a 30-second execution limit on the Pro plan (10 seconds on Hobby). The backend SSE stream is generated server-side and proxied. If the LLM response takes >30s, the Vercel function will timeout. 

**Mitigation:** The frontend connects directly to the backend SSE endpoint (not via a Vercel API route) — so this timeout only applies if a Vercel API route is used as a proxy. If connecting directly to Railway, no timeout concern.

**Build check:**
`npm run build` is verified by CI (`frontend-build` job in ci.yml) — ✅

**Vercel readiness: 8.5/10** — Deploy-ready with environment variable setup.

---

## 4. CI/CD Readiness

### Current state
- `.github/workflows/ci.yml` — 7 jobs, `ci-gate` summary job ✅
- `.github/workflows/release.yml` — Docker push to GHCR + GitHub Release on tags ✅
- Concurrency cancellation configured ✅
- Codecov integration documented ✅

### Gaps
- No deployment step in CI — release.yml builds the image but does not deploy to Railway or any environment
- No smoke test after deployment — could ship a broken release without knowing
- `mypy` is advisory (`continue-on-error: true`) — type errors don't block release
- Frontend lint is advisory — ESLint issues don't block CI

### Secrets required in GitHub repository settings

| Secret | Purpose |
|---|---|
| `GITHUB_TOKEN` | Auto-provided; GHCR push and release |
| `CODECOV_TOKEN` | Coverage upload |
| `RAILWAY_TOKEN` | (Not set up) For future Railway auto-deploy |

**CI/CD readiness: 7/10**

---

## 5. Database Migration Strategy

**Current:** `scripts/seed_db.py` runs `001_create_users.sql` and `003_seed_k8s_ops.sql` then ingests documents.

**Issues:**
- No migration versioning system (no Alembic, no Flyway)
- `seed_db.py` is not idempotent — running it twice may fail or create duplicates
- LangGraph `PostgresSaver.setup()` creates its own tables separately from `seed_db.py`
- No documented rollback procedure

**For production use beyond a single deployment, a proper migration system (Alembic or sqitch) is needed.**

---

## 6. Secrets and Security Configuration

**Secrets checklist:**
- [ ] `JWT_SECRET` — must be at least 32 random bytes (currently no minimum enforced)
- [ ] No hardcoded secrets found in any code file ✅
- [ ] `.env` is in `.gitignore` ✅
- [ ] `docker-compose.yml` uses `${VAR}` references, not literal secrets ✅
- [ ] `.env.example` contains only placeholder values ✅

**Risk:** `JWT_SECRET` has no minimum length validation in `Settings`. An operator could set it to an empty string or "secret" and the app would start silently with a weak token signing key.

---

## 7. Production Operations

### Monitoring
- `GET /admin/health` for uptime monitoring (pingdom, UptimeRobot, etc.) ✅
- Health checks Postgres, Qdrant, OpenAI, Redis — returns 503 if any critical service is down ✅
- Langfuse for AI call tracing (optional, feature-flagged) ✅
- JSON structured logging when `LOG_JSON=true` — compatible with Datadog, Papertrail ✅

### Missing
- No Prometheus metrics endpoint (`/metrics`) — cannot integrate with Grafana directly
- No APM integration (Datadog, New Relic)
- No alerting configuration

---

## 8. Deployment Readiness Scorecard

| Dimension | Score | Status |
|---|---|---|
| Docker Compose (local) | 7/10 | Works; needs `restart` policy + non-root user |
| Docker image quality | 6/10 | Missing non-root user, .dockerignore, large size |
| Railway backend | 7/10 | Ready with env vars; S3 storage required |
| Vercel frontend | 8.5/10 | Deploy-ready today |
| CI/CD pipeline | 7/10 | Solid; no deployment step |
| Database migrations | 5/10 | No versioned migration system |
| Secrets management | 7/10 | Good practices; JWT length not validated |
| Monitoring | 6/10 | Health endpoint only; no metrics |
| **Overall** | **6.8/10** | Deployable for private beta; not hardened for open traffic |

---

## 9. Deployment Blockers (Ordered by Priority)

| # | Blocker | Required For | Fix |
|---|---|---|---|
| 1 | No `restart: unless-stopped` | Any production uptime | Add to docker-compose.yml |
| 2 | Container runs as root | Any shared hosting | Add `USER appuser` to Dockerfile |
| 3 | No `.dockerignore` | Clean reproducible builds | Add `.dockerignore` file |
| 4 | No connection pooling | >10 concurrent users | Add `psycopg_pool` or SQLAlchemy |
| 5 | Knowledge Base upload unimplemented | Product completeness | Implement `/documents/upload` |
| 6 | `JWT_SECRET` length not validated | Production security | Add Pydantic `@field_validator` |
