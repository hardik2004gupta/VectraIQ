# RELEASE_CHECKLIST.md — VectraIQ Phase 5

**Date:** 2026-06-30

Use this checklist before tagging a public release.

---

## Pre-release Verification

### Backend

- [ ] `make lint` passes (ruff check + format)
- [ ] `make test` passes — all tests green, no skips without reason
- [ ] `make test` coverage ≥ 70% on `vectraiq/api/` and `vectraiq/middleware/`
- [ ] `docker compose up` starts without errors
- [ ] `GET /admin/health` returns `200 {"status": "ok"}` with all services running
- [ ] `POST /auth/register` creates a new user
- [ ] `POST /auth/login` returns a valid JWT
- [ ] `POST /query` returns an answer for "How do I restart a Kubernetes pod?"
- [ ] `POST /query/stream` returns SSE frames with `status` → `result` → `done`
- [ ] `GET /docs` renders Swagger UI correctly
- [ ] `GET /admin/cache/stats` returns cache tier data (admin token)
- [ ] `POST /admin/cache/clear` clears in-memory cache (admin token)

### Frontend

- [ ] `npm run build` succeeds with no TypeScript errors
- [ ] `npm run type-check` passes
- [ ] Landing page loads at `http://localhost:3000`
- [ ] Login form authenticates and redirects to dashboard
- [ ] Registration form creates a new account
- [ ] Dashboard shows health status and cache stats
- [ ] Chat page accepts a question and shows streaming status updates
- [ ] Chat page renders markdown (bold, code blocks, lists)
- [ ] SQL approval card appears on a SQL-intent query
- [ ] Analytics page shows charts
- [ ] Settings page shows system health and clears cache
- [ ] Knowledge Base page shows drag-and-drop zone
- [ ] Sidebar navigation works on all pages
- [ ] Logout clears session and redirects to login

### Security

- [ ] `GET /query` without a JWT token → 403
- [ ] `GET /admin/cache/stats` with user (non-admin) token → 403
- [ ] Question with injection pattern `ignore previous instructions` → 422
- [ ] `LANGFUSE_ENABLED=false` disables tracing (no Langfuse import errors)
- [ ] Security headers present on all responses (`X-Frame-Options: DENY`, etc.)
- [ ] CORS preflight with `http://attacker.com` origin is rejected
- [ ] `pip-audit` shows no HIGH or CRITICAL vulnerabilities
- [ ] `npm audit --audit-level=high` shows no HIGH vulnerabilities

### Docker

- [ ] `docker compose build` succeeds from a clean checkout
- [ ] `docker compose up` brings up all 3 services (postgres, qdrant, app)
- [ ] App healthcheck (`docker compose ps`) shows `healthy` after startup
- [ ] `docker compose exec app python scripts/seed_db.py` completes
- [ ] No secrets or credentials in Docker image layers (`docker history <image>`)

### CI/CD

- [ ] `.github/workflows/ci.yml` `ci-gate` job is passing on `main`
- [ ] `CODECOV_TOKEN` is set in repository secrets
- [ ] Branch protection rule requires `ci-gate` to pass before merge

---

## Known Open Issues (acceptable for release)

| ID | Issue | Severity | Workaround |
|---|---|---|---|
| KB-001 | `/documents/upload` endpoint not implemented | Medium | Use `make seed` to ingest documents via CLI |
| SEC-001 | SQL approval not user-scoped | Medium | SQL queries require explicit user action to trigger |
| CACHE-001 | Redis `cache.clear()` no-op for remote entries | Low | In-memory cache is cleared; Redis entries expire by TTL |
| AUTH-001 | No refresh token flow | Low | Users must re-login after JWT expiry (60 min default) |

---

## Release Steps

```bash
# 1. Ensure main is green
git checkout main && git pull

# 2. Update version in pyproject.toml and frontend/package.json
# Edit: version = "x.y.z"

# 3. Update CHANGELOG_PHASE5.md with release date

# 4. Commit
git add pyproject.toml frontend/package.json CHANGELOG_PHASE5.md
git commit -m "chore: bump version to vx.y.z"

# 5. Tag
git tag -a vx.y.z -m "Release vx.y.z"
git push origin main --tags

# 6. GitHub Actions release.yml will:
#    - Build + push Docker image to GHCR
#    - Create GitHub Release with auto-generated notes
```

---

## Post-release

- [ ] Verify Docker image is accessible at `ghcr.io/hardik-gupta/vectraiq:x.y.z`
- [ ] Verify GitHub Release page is public with correct tag
- [ ] Update `README.md` badge URLs if repository was transferred
- [ ] Announce in project discussion or README if community release
