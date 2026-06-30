# CI_CD_GUIDE.md — VectraIQ Phase 5

**Date:** 2026-06-30

---

## Workflow Overview

Two GitHub Actions workflows:

| Workflow | File | Trigger | Jobs |
|---|---|---|---|
| CI | `.github/workflows/ci.yml` | Push to main/master/develop; PRs to main | lint, typecheck, tests, frontend lint, frontend build, Docker build, security scan, gate |
| Release | `.github/workflows/release.yml` | Push of `v*.*.*` tag | Docker push to GHCR, GitHub Release |

---

## CI Pipeline (`ci.yml`)

### Jobs

```
backend-lint ──────────┐
backend-typecheck ─────┤
backend-tests ─────────┼──► ci-gate
frontend-lint ─────────┤
frontend-build ────────┤
docker-build ──────────┘
     └── security-scan (advisory, not blocking)
```

### `backend-lint`

```yaml
uv run ruff check vectraiq/ tests/
uv run ruff format --check vectraiq/ tests/
```

Fails the build on any lint or formatting violation. Run locally with `make lint` and `make format`.

### `backend-typecheck`

```yaml
uv run mypy vectraiq/ --ignore-missing-imports
```

Currently `continue-on-error: true` — advisory only. Will be made blocking once type coverage is complete.

### `backend-tests`

Spins up a PostgreSQL 16 service container. Runs:
```bash
pytest tests/ --tb=short -v --junitxml=test-results/junit.xml \
  --cov=vectraiq --cov-report=xml:coverage.xml -m "not integration"
```

Uploads coverage to Codecov. Uploads JUnit XML as artifact for PR annotations.

**Environment variables set by CI:**
```yaml
JWT_SECRET: ci-test-secret-do-not-use-in-prod
OPENAI_API_KEY: sk-test-placeholder
DATABASE_URL: postgresql://postgres:postgres@localhost:5432/vectraiq_test
QDRANT_URL: http://localhost:6333
LOG_LEVEL: WARNING
```

Note: All external I/O is mocked; `OPENAI_API_KEY` is a placeholder (never called in tests).

### `frontend-lint`

```bash
npm run type-check   # tsc --noEmit
npm run lint         # next lint
```

`lint` is `continue-on-error: true` until ESLint config is finalized. `type-check` is blocking.

### `frontend-build`

```bash
npm run build   # next build
```

Verifies the Next.js production build completes successfully. Build artifact is uploaded (retained 1 day).

### `docker-build`

Builds the Docker image without pushing. Uses GitHub Actions cache (`type=gha`) for layer caching. Tags as `vectraiq:ci-<sha>`.

### `security-scan`

- Runs `pip-audit` on locked dependencies (advisory — does not block CI)
- Runs `npm audit --audit-level=high` on frontend dependencies (advisory)

### `ci-gate`

A summary job that depends on `backend-lint`, `backend-tests`, `frontend-build`, and `docker-build`. Branch protection rules should require this job to pass.

---

## Release Pipeline (`release.yml`)

Triggered by pushing a version tag:
```bash
git tag v1.2.3
git push origin v1.2.3
```

### Jobs

1. **Build & Push Docker Image** — builds and pushes to GitHub Container Registry (`ghcr.io`)
   - Tags: `v1.2.3`, `1.2`, `sha-<sha>`
   - Uses GHA layer cache for fast rebuilds
   
2. **Create GitHub Release** — creates a release with auto-generated notes from commit history
   - Marks as `prerelease` if tag contains `-rc`, `-beta`, or `-alpha`

### Required Secrets

| Secret | Where to set | Value |
|---|---|---|
| `GITHUB_TOKEN` | Auto-provided | Used for GHCR push and release creation |
| `CODECOV_TOKEN` | Repository Settings → Secrets | From [codecov.io](https://codecov.io) |

---

## Local Setup for CI Parity

Run the same checks locally before pushing:

```bash
# Backend
make lint          # ruff check + format check
make test          # pytest with coverage

# Frontend
cd frontend
npm run type-check
npm run build
```

---

## Branch Protection (Recommended)

In GitHub Settings → Branches → Protect `main`:

- [x] Require status checks: `ci-gate`
- [x] Require branches to be up to date before merging
- [x] Require linear history
- [x] Do not allow bypassing the above settings for admins

---

## Deployment

### Vercel (Frontend)

1. Import the repository in Vercel
2. Set **Root Directory** to `frontend`
3. Framework: Next.js (auto-detected)
4. Environment variable: `NEXT_PUBLIC_API_URL=https://your-api.railway.app`
5. Deploy on push to `main`

### Railway (Backend)

1. Create a new Railway project
2. Add a service from GitHub — select this repository
3. Set **Start Command** to `python scripts/serve.py` (or use `Procfile`)
4. Set all environment variables (see `.env.example`)
5. Add PostgreSQL and Redis services from Railway's marketplace
6. Set `FRONTEND_ORIGINS=https://your-app.vercel.app`

### Docker Compose (Self-hosted)

```bash
# Production
LOG_JSON=true FRONTEND_ORIGINS=https://your-domain.com docker compose up -d
```

---

## Concurrency

All CI jobs use:
```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

This cancels in-progress CI runs when a new commit is pushed to the same branch, preventing queue buildup on fast-iteration branches.
