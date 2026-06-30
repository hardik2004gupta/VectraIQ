# Deployment Guide

## Option 1 — Docker Compose (Self-Hosted, Recommended)

The easiest path. Runs Postgres, Qdrant, and the VectraIQ API in a single `docker compose up`.

### Prerequisites

- Docker Desktop (or Docker Engine + Compose plugin)
- OpenAI API key
- Upstash Redis account (optional — in-memory fallback used if absent)

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/your-username/vectraiq.git
cd vectraiq

# 2. Configure environment
cp .env.example .env
# Edit .env — at minimum set OPENAI_API_KEY and JWT_SECRET

# 3. Start all services
docker compose up -d

# 4. Wait for healthy status
docker compose ps   # all services should show "healthy"

# 5. Run database migrations + ingest K8s documents
docker compose exec app python scripts/seed_db.py

# 6. Verify
curl http://localhost:8000/admin/health
```

The API is now running at `http://localhost:8000`.  
Swagger UI is available at `http://localhost:8000/docs`.

### Production docker-compose additions

For any production deployment, add these to `docker-compose.yml`:

```yaml
# On every service block:
restart: unless-stopped

# On the app service:
deploy:
  resources:
    limits:
      memory: 4G
      cpus: '2'
```

---

## Option 2 — Railway (Backend) + Vercel (Frontend)

### Backend on Railway

1. Create a new Railway project
2. Add a service from GitHub → select this repository
3. Set **Start Command**: `python scripts/serve.py`
4. Add a **PostgreSQL** addon (Railway provides this)
5. Add environment variables (see [Environment Variables](#environment-variables) below)
6. Set `FRONTEND_ORIGINS=https://your-app.vercel.app`
7. After first deploy, run migrations: `python scripts/seed_db.py`

> **Note:** Set `STORAGE_BACKEND=s3` on Railway — the ephemeral filesystem does not persist across deploys.

### Frontend on Vercel

1. Import the repository in Vercel
2. Set **Root Directory** to `frontend`
3. Framework: Next.js (auto-detected)
4. Set environment variable: `NEXT_PUBLIC_API_URL=https://your-api.railway.app`
5. Deploy

---

## Environment Variables

### Required

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | OpenAI API key for LLM + embeddings |
| `JWT_SECRET` | Secret for signing JWT tokens (min 32 chars, random) |
| `DATABASE_URL` | PostgreSQL connection string |
| `QDRANT_URL` | Qdrant instance URL (e.g. `http://localhost:6333`) |

### Optional

| Variable | Default | Description |
|---|---|---|
| `UPSTASH_REDIS_URL` | — | Upstash Redis HTTP URL (in-memory fallback if absent) |
| `UPSTASH_REDIS_TOKEN` | — | Upstash Redis token |
| `TAVILY_API_KEY` | — | Tavily API key for CRAG web search fallback |
| `VOYAGE_API_KEY` | — | Voyage AI key (for Voyage reranker backend) |
| `RERANKER_BACKEND` | `crossencoder` | `crossencoder` or `voyage` |
| `STORAGE_BACKEND` | `local` | `local` or `s3` |
| `AWS_S3_BUCKET` | — | S3 bucket name (if `STORAGE_BACKEND=s3`) |
| `LANGFUSE_SECRET_KEY` | — | Langfuse secret key (tracing disabled if absent) |
| `LANGFUSE_PUBLIC_KEY` | — | Langfuse public key |
| `LOG_JSON` | `false` | Set `true` for structured JSON logging (production) |
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `FRONTEND_ORIGINS` | `http://localhost:3000` | Comma-separated allowed CORS origins |

See `.env.example` for the complete list with descriptions.

---

## Ingesting Documents

VectraIQ ships with a Kubernetes documentation corpus in `seed/docs/true_data/`. To ingest your own documents, add files (PDF, DOCX, HTML, TXT, MD) to `seed/docs/true_data/` and re-run:

```bash
python scripts/seed_db.py
```

This script:
1. Runs SQL migrations (`seed/migrations/`)
2. Creates default users
3. Parses all documents with Docling
4. Chunks, embeds (OpenAI), and upserts into Qdrant

---

## Health Check

```bash
curl http://localhost:8000/admin/health
```

Returns `200 OK` when all critical services (Postgres, Qdrant, OpenAI) are reachable.  
Returns `503 Service Unavailable` when any critical service is down (Redis is non-critical).

---

## Running the Evaluation Suite

```bash
make eval-baseline   # Naive dense-only profile
make eval-all        # All features enabled
make eval            # Both + diff report
```

Results are written to `eval/results/` as JSON files.

---

## CI/CD

The repository ships with two GitHub Actions workflows:

| Workflow | Trigger | What it does |
|---|---|---|
| `ci.yml` | Push to main/PR | Lint, typecheck, tests, Docker build, security scan |
| `release.yml` | Push of `v*.*.*` tag | Build + push Docker image to GHCR, create GitHub Release |

### Releasing

```bash
git tag v1.0.0
git push origin v1.0.0
# GitHub Actions publishes the Docker image and creates the release automatically
```
