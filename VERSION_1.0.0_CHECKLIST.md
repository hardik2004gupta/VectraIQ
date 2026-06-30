# VectraIQ v1.0.0 — Release Checklist

Use this checklist to verify the release is complete before tagging and publishing.

---

## Code Quality

- [x] All Critical severity issues resolved (0 remaining)
- [x] All High severity issues resolved (0 remaining)
- [x] Version is `1.0.0` in `pyproject.toml`
- [x] Version is `1.0.0` in `vectraiq/main.py` (`create_app()`)
- [x] Version is `1.0.0` in `frontend/package.json`
- [x] No internal development comments in `pyproject.toml`
- [x] No hardcoded secrets in any committed file
- [x] `ruff check vectraiq/` passes (or known exceptions documented)
- [x] `ruff format --check vectraiq/` passes
- [ ] `mypy vectraiq/` passes (advisory — `continue-on-error: true` in CI)

## Security

- [x] Docker container runs as non-root user (`appuser`, UID 1001)
- [x] `.env` and `.env.*` excluded from git via `.gitignore`
- [x] `.env` and `.env.*` excluded from Docker build context via `.dockerignore`
- [x] `.env.example` present with no real credentials
- [x] JWT_SECRET is required (runtime check) — no default insecure value
- [x] All dependencies pinned with `>=` lower bounds in `pyproject.toml`
- [x] `pip-audit` runs in CI (security scan job)
- [x] `npm audit --audit-level=high` runs in CI

## Infrastructure

- [x] `Dockerfile` builds successfully
- [x] `.dockerignore` present and excludes `.git`, `frontend/`, test artifacts
- [x] `docker compose up` starts all services successfully
- [x] All Docker Compose services have `restart: unless-stopped`
- [x] All Docker Compose services have health checks
- [x] `app` service waits for `postgres` and `qdrant` to be healthy before starting
- [x] `HEALTHCHECK` defined in `Dockerfile`
- [x] `postgres:16-alpine` (not `:latest`)
- [x] `qdrant/qdrant:v1.17.0` (pinned version, not `:latest`)

## CI/CD

- [x] `.github/workflows/ci.yml` is present
- [x] CI runs on `push` to `main`, `master`, `develop`
- [x] CI runs on pull requests targeting `main`, `master`
- [x] Concurrency cancellation configured (no redundant runs)
- [x] `backend-lint` job passes
- [x] `backend-tests` job runs (passes vacuously — no tests yet)
- [x] `frontend-lint` job passes (type-check + ESLint)
- [x] `frontend-build` job produces a successful Next.js build
- [x] `docker-build` job builds image without error
- [x] `security-scan` job runs pip-audit and npm audit
- [x] `ci-gate` job depends on all required checks
- [x] No `npm ci` in CI (uses `npm install` — no `package-lock.json` exists)

## Backend

- [x] `vectraiq/` package present and importable
- [x] FastAPI app starts with `uvicorn vectraiq.main:create_app --factory`
- [x] `GET /admin/health` returns 200 with component status
- [x] `POST /auth/register` creates a user
- [x] `POST /auth/login` returns a JWT
- [x] `POST /query` requires JWT and returns a `ChatResponse`
- [x] `POST /query/stream` returns SSE events
- [x] LangGraph `PostgresSaver` checkpointing configured
- [x] `asyncio.get_running_loop()` used (not deprecated `get_event_loop()`)
- [x] `psycopg2-binary` (v2) in `pyproject.toml` (for auth/admin/sql routes)
- [x] `psycopg[binary]` (v3) in `pyproject.toml` (for LangGraph PostgresSaver)
- [x] `local_storage.py` is fully implemented (not empty)
- [x] Structured JSON logging enabled in production (`LOG_JSON=true`)

## Frontend

- [x] `npm run build` succeeds with no errors
- [x] `npm run type-check` passes
- [x] Login page renders and submits to `POST /auth/login`
- [x] Register page renders and submits to `POST /auth/register`
- [x] Chat page connects to SSE stream via `POST /query/stream`
- [x] Chat history persists to `localStorage` (survives page refresh)
- [x] Knowledge Base page shows honest "Coming Soon" banner (no fake toast)
- [x] Analytics page uses CSS variables (no hardcoded hex colors)
- [x] `layout.tsx` includes `icons` metadata (favicon)
- [x] `layout.tsx` includes `robots` metadata
- [x] `frontend/public/icon.svg` exists (SVG favicon)
- [x] All pages have ARIA labels on interactive elements
- [x] Loading skeletons shown while data fetches

## Documentation

- [x] `README.md` — architecture overview, quickstart, feature matrix, badges
- [x] `CHANGELOG.md` — Keep-a-Changelog format, v1.0.0 entry present
- [x] `docs/architecture.md` — system design, sequence diagrams
- [x] `docs/deployment.md` — Docker, production checklist, environment variables
- [x] `CODE_OF_CONDUCT.md` — Contributor Covenant v2.1
- [x] `CONTRIBUTING.md` — PR workflow, coding standards, development setup
- [x] `.env.example` — all required and optional env vars documented
- [x] `FINAL_RELEASE_REPORT.md` — present
- [x] `FINAL_SCORECARD.md` — present
- [x] `FINAL_FIX_LOG.md` — present
- [x] `KNOWN_LIMITATIONS.md` — present
- [x] `RELEASE_NOTES_v1.0.0.md` — present
- [x] `VERSION_1.0.0_CHECKLIST.md` — present (this file)

## Open Source

- [x] `LICENSE` — MIT license, correct year
- [x] GitHub repository description and topics set
- [x] `.github/ISSUE_TEMPLATE/` — bug report + feature request templates
- [x] No sensitive data in any committed file (verify with `git log --all --full-history -- "*.env"`)
- [x] No binaries or large files committed (no `.pyc`, `.pyo`, `node_modules`)

## Git

- [x] All changes committed to `master` branch
- [x] `git log --oneline` shows clean, descriptive commit messages
- [x] Remote `origin` is `https://github.com/hardik2004gupta/VectraIQ.git`
- [ ] **TAG:** `git tag -a v1.0.0 -m "VectraIQ v1.0.0 — Initial public release"`
- [ ] **PUSH TAG:** `git push origin v1.0.0`
- [ ] **GitHub Release:** Created from tag `v1.0.0` with `RELEASE_NOTES_v1.0.0.md` as body

---

## Sign-off

| Role | Name | Date | Status |
|---|---|---|---|
| Principal Engineer | Hardik Gupta | 2026-06-30 | ✅ Approved |
| Release Audit | VectraIQ Final Release Cycle | 2026-06-30 | ✅ Approved |

---

*VectraIQ v1.0.0 Release Checklist — 2026-06-30*
