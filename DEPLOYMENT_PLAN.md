# VectraIQ v2 — Deployment Plan
**Version:** 2.0  
**Status:** Design Phase  

---

## Service Topology

```
┌──────────────────────────────────────────────────────────────────┐
│                         INTERNET                                  │
└──────────────────┬───────────────────────────┬───────────────────┘
                   │                           │
          ┌────────▼──────────┐    ┌──────────▼──────────┐
          │  Vercel (CDN/Edge)│    │   Railway (API)      │
          │  apps/web         │    │   apps/api           │
          │  Next.js 14       │───▶│   FastAPI + uvicorn  │
          └───────────────────┘    └──────────┬───────────┘
                                              │
          ┌───────────────────────────────────┼───────────────────┐
          │                                   │                   │
 ┌────────▼──────┐  ┌──────────────┐  ┌─────▼──────┐  ┌────────▼──────┐
 │  Neon Postgres│  │ Qdrant Cloud │  │Upstash Redis│  │Cloudflare R2  │
 │  (serverless) │  │  (managed)   │  │  (HTTP)     │  │  (S3-compat)  │
 └───────────────┘  └──────────────┘  └─────────────┘  └───────────────┘
          │
 ┌────────▼──────┐  ┌──────────────┐
 │  OpenAI API   │  │  Tavily API  │
 │  (LLM + embed)│  │ (web search) │
 └───────────────┘  └──────────────┘
```

---

## Service Overview

| Service | Provider | Purpose | Tier |
|---|---|---|---|
| Frontend | Vercel | Next.js 14 SPA/SSR | Free → Pro |
| API | Railway | FastAPI Python | Hobby → Pro |
| PostgreSQL | Neon | User data, SQL knowledge base | Free → Launch |
| Vector DB | Qdrant Cloud | Embeddings | Free → Starter |
| Redis | Upstash | Caching, rate limits, token budget | Free → Pay-per-use |
| Object Storage | Cloudflare R2 | Document file storage | Free (10 GB) |
| LLM | OpenAI | GPT-4o + embeddings | Pay-per-use |
| Web Search | Tavily | CRAG fallback | Free → Standard |
| Error Tracking | Sentry (optional) | Error reporting | Free |

---

## Local Development

### Docker Compose (Full Stack)

`docker-compose.yml` runs all infrastructure locally. Cloud services (OpenAI, Tavily) require real API keys even in dev — they cannot be mocked for useful testing.

```yaml
# What docker-compose provides locally:
services:
  api:       FastAPI on :8000 (hot reload via --reload)
  web:       Next.js dev server on :3000 (hot reload)
  postgres:  Postgres 16 on :5432
  qdrant:    Qdrant on :6333 + :6334
  redis:     Redis 7 on :6379

# Persistent volumes:
  postgres_data, qdrant_data, redis_data
```

### Makefile Commands

```
make dev          # docker compose up --build
make dev-api      # API only (skip web)
make dev-web      # Web only (skip API)
make migrate      # run seed/migrations/ in order
make seed         # seed demo data (scripts/seed_db.py)
make test         # pytest apps/api/tests/
make test-e2e     # playwright tests
make lint         # ruff + mypy + eslint
make build        # docker build for production image
```

### Local Environment Variables

```bash
# apps/api/.env.local (git-ignored)
POSTGRES_URL=postgresql+psycopg://vectraiq:vectraiq@localhost:5432/vectraiq
QDRANT_URL=http://localhost:6333
REDIS_URL=redis://localhost:6379
STORAGE_BACKEND=local
LOCAL_STORAGE_PATH=/tmp/vectraiq/documents
JWT_SECRET=local-dev-secret-at-least-32-chars-long
OPENAI_API_KEY=sk-...
TAVILY_API_KEY=tvly-...
LLM_GUARD_ENABLED=false   # disable in local dev to skip heavy model loads
ENVIRONMENT=development

# apps/web/.env.local (git-ignored)
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### First-Time Setup Script

```bash
# scripts/dev_setup.sh
#!/usr/bin/env bash
set -e

echo "1. Checking Docker..."
docker compose version

echo "2. Starting infrastructure..."
docker compose up -d postgres qdrant redis

echo "3. Waiting for Postgres..."
until pg_isready -h localhost -p 5432 -U vectraiq; do sleep 1; done

echo "4. Running migrations..."
make migrate

echo "5. Seeding demo data..."
make seed

echo "6. Starting API + Web..."
docker compose up api web
```

---

## Environment Variables

### Complete Variable Reference

```bash
# ─── Database ───────────────────────────────────────────────────────
POSTGRES_URL=postgresql+psycopg://user:pass@host:5432/vectraiq
# For async: postgresql+psycopg_async://... (same credentials)

# ─── Vector DB ─────────────────────────────────────────────────────
QDRANT_URL=https://xxx.cloud.qdrant.io:6333
QDRANT_API_KEY=...                    # required for Qdrant Cloud
QDRANT_COLLECTION=vectraiq_v2         # default

# ─── Cache ─────────────────────────────────────────────────────────
REDIS_URL=rediss://...upstash.io:6380  # rediss:// for TLS
REDIS_TOKEN=...                         # Upstash REST token

# ─── Storage ────────────────────────────────────────────────────────
STORAGE_BACKEND=r2                      # r2 | s3 | local
R2_ACCOUNT_ID=...
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_BUCKET_NAME=vectraiq-documents
# OR for AWS S3:
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_S3_BUCKET=vectraiq-documents
AWS_REGION=us-east-1

# ─── AI Providers ───────────────────────────────────────────────────
OPENAI_API_KEY=sk-...
OPENAI_LLM_MODEL=gpt-4o
OPENAI_EMBEDDING_MODEL=text-embedding-3-large
OPENAI_EMBEDDING_DIM=3072
TAVILY_API_KEY=tvly-...

# ─── Auth ────────────────────────────────────────────────────────────
JWT_SECRET=...  # REQUIRED: minimum 32 chars, random
JWT_ALGORITHM=HS256
JWT_EXPIRY_HOURS=24

# ─── Security ────────────────────────────────────────────────────────
LLM_GUARD_ENABLED=true
RATE_LIMIT_PER_MINUTE=20
TOKEN_BUDGET_DAILY=100000

# ─── Feature Flags ──────────────────────────────────────────────────
DEFAULT_RERANK_ENABLED=true
DEFAULT_HYBRID_ENABLED=true
DEFAULT_CRAG_ENABLED=true
DEFAULT_HYDE_ENABLED=false
DEFAULT_SELF_RAG_ENABLED=false

# ─── Observability ──────────────────────────────────────────────────
SENTRY_DSN=...                          # optional
LOG_LEVEL=INFO                          # DEBUG | INFO | WARNING | ERROR
ENVIRONMENT=production                  # development | staging | production

# ─── Frontend (NEXT_PUBLIC_ prefix = exposed to browser) ─────────────
NEXT_PUBLIC_API_URL=https://api.vectraiq.com
```

### Environment Management Strategy

```
Environments:      development → staging → production
Configuration:     .env.local (git-ignored) for dev
                   Railway/Vercel env vars UI for staging + prod
Secrets rotation:  JWT_SECRET rotation requires a rolling restart
                   (all existing tokens invalidate — warn users)
Sensitive vars:    JWT_SECRET, *_API_KEY, *_SECRET — never in code
```

---

## Railway (API Deployment)

### Service Configuration

```
Runtime:     Python 3.12
Start command: uvicorn apps.api.src.main:app --host 0.0.0.0 --port $PORT --workers 2
Build command: pip install -e ".[prod]"
Health check:  GET /api/v1/health (200 = healthy)
```

### Dockerfile (Production)

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install system deps for psycopg binary + sentence-transformers
RUN apt-get update && apt-get install -y \
    libpq-dev gcc curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[prod]"

COPY apps/api/ apps/api/
COPY seed/ seed/

# Non-root user
RUN useradd -m vectraiq && chown -R vectraiq /app
USER vectraiq

EXPOSE 8000
CMD ["uvicorn", "apps.api.src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

### Railway-Specific Notes

- Railway auto-injects `$PORT` — do NOT hardcode 8000
- 512 MB RAM on Hobby tier; CrossEncoder model requires ~350 MB — upgrade to Standard (1 GB) for AI features
- Cold starts on Hobby (no persistent storage) — documents stored in R2, not filesystem
- Set `RAILWAY_DOCKERFILE_PATH=Dockerfile` in Railway service settings

---

## Vercel (Frontend Deployment)

### Configuration

```json
// apps/web/vercel.json
{
  "buildCommand": "pnpm build",
  "outputDirectory": ".next",
  "installCommand": "pnpm install",
  "framework": "nextjs"
}
```

### Environment Variables (Vercel UI)

```
NEXT_PUBLIC_API_URL  = https://api.vectraiq.up.railway.app
```

### Notes

- Enable "Edge Runtime" for the root layout for fastest global TTFB
- API routes in `apps/web/src/app/api/` act as a BFF (Backend-for-Frontend) proxy — they add the bearer token from the session cookie before forwarding to the Railway API
- This avoids exposing the JWT to client-side JavaScript

---

## CI/CD — GitHub Actions

### Workflow: `.github/workflows/ci.yml`

```
Trigger: push to main, PRs to main

Jobs (parallel):
  lint-api:
    - ruff check apps/api/
    - mypy apps/api/
  
  lint-web:
    - eslint apps/web/
    - tsc --noEmit

  test-api:
    services: postgres:16, qdrant:latest, redis:7
    steps:
      - pytest apps/api/tests/ -v --cov=apps/api/src

  test-web:
    steps:
      - pnpm test (Vitest unit tests)

  # Only on push to main:
  deploy-api:
    needs: [lint-api, test-api]
    steps:
      - railway up --service api

  deploy-web:
    needs: [lint-web, test-web]
    steps:
      - vercel deploy --prod
```

### Workflow: `.github/workflows/eval.yml`

```
Trigger: scheduled (weekly, Sunday midnight)
         manual dispatch

steps:
  - python eval/run_eval.py --profile all
  - Upload eval/results/ as artifact
  - Post summary comment to PR (if triggered by PR)
```

### Branch Strategy

```
main        → production (Railway + Vercel)
staging     → staging environment (Railway staging service)
feat/*      → feature branches (CI only, no deploy)
```

---

## Testing Strategy

### Unit Tests (pytest, Vitest)

- Location: `apps/api/tests/unit/` and `apps/web/src/**/*.test.ts`
- Coverage target: 80% of application + domain layers
- Mock external services (OpenAI, Tavily) with pytest fixtures
- Real Postgres and Qdrant via Docker testcontainers

**Key test categories:**
- AI modules: Router, Retriever, Reranker, Generator — unit tested with fixed inputs
- Security: InputGuard, OutputGuard, SQLValidator — unit tested with adversarial prompts
- Cache: Cache namespace logic, TTL, invalidation
- Schemas: Pydantic model validation with edge cases
- SQL validator: `is_select_only()` with 20+ test cases (DROP, UPDATE, comment injection, semicolons)

### Integration Tests

- Location: `apps/api/tests/integration/`
- Test full use case flow (QueryUseCase end-to-end) with real Postgres + Qdrant
- Do NOT use mocks for database or vector store in integration tests (lesson from v1 eval — mocks hide real bugs)
- Test LangGraph state transitions with SQL approval interrupt flow

### End-to-End Tests (Playwright)

- Location: `apps/web/e2e/`
- Scenarios:
  - Login → chat → receive answer
  - Upload document → wait for indexed status → query document
  - SQL query → see approval card → approve → see result
  - Feature toggles persist after refresh

### Golden Eval Suite

- Location: `eval/seed_questions.yaml` (40 questions, NEVER delete)
- Run weekly in CI: `python eval/run_eval.py --profile all`
- Metrics: RAGAS (context_precision, answer_relevance, faithfulness)
- Profiles: naive, sparse_only, hybrid, hybrid+rerank, hybrid+rerank+hyde, hybrid+rerank+crag, all
- Threshold: if any profile's answer_relevance drops >5% vs. baseline, fail CI

---

## Documentation Strategy

### Auto-generated

- **API docs:** FastAPI generates `/docs` (Swagger) and `/redoc` automatically from Pydantic schemas and route docstrings
- **Type docs:** TypeDoc for frontend TypeScript types

### Maintained in `docs/`

```
docs/
  getting-started.md    → local setup in 10 minutes
  architecture.md       → link to ARCHITECTURE_V2.md
  api-reference.md      → hand-written examples for key endpoints
  deployment.md         → link to DEPLOYMENT_PLAN.md
  configuration.md      → all env vars with types and defaults
  ai-features.md        → user-facing guide (Hybrid, HyDE, CRAG, Self-RAG, SQL)
  contributing.md       → PR process, code style, test requirements
```

### CLAUDE.md

Auto-loaded by Claude Code on every session. Kept current. Documents:
- Known critical issues
- Service topology
- Useful commands
- File status (KEEP/REFACTOR/DELETE tags)

---

## Monitoring in Production

### Health Endpoints

```
GET /api/v1/health
→ 200: { status: "ok", services: { postgres: "ok", qdrant: "ok", redis: "ok" } }
→ 503: any service unreachable

GET /api/v1/metrics   (admin only)
→ cache hit rates, query counts, average latency (last 1000 requests)
```

### Recommended Uptime Monitor

- Better Uptime or UptimeRobot: ping `/api/v1/health` every 60s
- Alert channel: email or Slack webhook on 2 consecutive failures

### Key Metrics to Watch

| Metric | Warning | Critical |
|---|---|---|
| P95 query latency | > 5s | > 10s |
| Cache hit rate | < 60% | < 40% |
| Error rate | > 1% | > 5% |
| Token budget exhaustion | 80% consumed | 95% consumed |
| Qdrant vectors | > 80% of tier limit | > 95% |

---

## Cost Estimates (Monthly)

### Free Tier (Development / Demo)

| Service | Free Tier | Limit |
|---|---|---|
| Vercel | Free | 100 GB bandwidth |
| Railway | $5 hobby | 500 MB RAM |
| Neon | Free | 0.5 GB storage |
| Qdrant Cloud | Free | 1 GB, 1M vectors |
| Upstash Redis | Free | 10K commands/day |
| Cloudflare R2 | Free | 10 GB storage |
| **Total infrastructure** | **~$5/month** | |

OpenAI costs (variable): ~$0.01–0.10 per query depending on enabled features

### Production Tier (~1,000 queries/day)

| Service | Plan | Cost |
|---|---|---|
| Vercel | Pro | $20/month |
| Railway | Standard (1 GB) | $20/month |
| Neon | Launch (10 GB) | $19/month |
| Qdrant Cloud | Starter | $25/month |
| Upstash Redis | Pay-per-use | ~$5/month |
| Cloudflare R2 | Standard | ~$2/month |
| **Total infrastructure** | | **~$91/month** |
| OpenAI (variable) | | ~$50–200/month |

---

## Rollback Procedure

### API Rollback
```bash
# Railway: previous deployment is kept for 24h
railway rollback --service api

# If database migration caused issues:
# 1. Roll back app first (above)
# 2. Apply reverse migration SQL manually
# 3. Never auto-rollback DB (too risky)
```

### Frontend Rollback
```bash
# Vercel keeps all deployments
# Promote previous deployment to production in Vercel UI
# Takes ~30 seconds
```

### Emergency Cache Clear
```bash
# If cached bad data is being served:
POST /api/v1/admin/cache/clear
Authorization: Bearer <admin-token>
Body: { "namespace": "rag_answer" }   # or "all" for full clear
```
