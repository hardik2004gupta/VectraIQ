# Contributing to VectraIQ

Thank you for your interest in contributing. This document covers the developer workflow.

## Prerequisites

- Python 3.12+
- Node.js 20+
- `uv` package manager (`pip install uv`)
- Docker + Docker Compose (for full-stack testing)
- PostgreSQL 16, Qdrant (or use `docker compose up`)

## Setup

```bash
git clone https://github.com/<your-org>/vectraiq.git
cd vectraiq

# Backend
make install        # creates .venv + installs all deps via uv

# Frontend
cd frontend
npm install

# Environment
cp .env.example .env
# Fill in OPENAI_API_KEY, JWT_SECRET (min 32 chars), DATABASE_URL, QDRANT_URL

# Database + document ingestion
make seed
```

## Development Workflow

```bash
# Run backend + frontend concurrently
make api            # FastAPI at :8000
cd frontend && npm run dev   # Next.js at :3000
```

## Running Tests

```bash
make test           # pytest (no external services required — all mocked)
```

Frontend type check:
```bash
cd frontend && npm run type-check
```

## Code Style

Backend:
- `ruff check` — enforced in CI (run `make lint`)
- `ruff format` — enforced in CI (run `make format`)
- No bare `except:` clauses; catch specific exceptions
- All new functions must have type annotations

Frontend:
- TypeScript strict mode — all `any` must be justified
- Use CSS custom properties (`var(--color-*)`) for colors; no hardcoded hex in JSX
- Components are Client Components by default; only use RSC when there is no state

## Pull Request Process

1. Fork the repository and create a branch: `git checkout -b feat/your-feature`
2. Make your changes following the style guide above
3. Run `make test` and `make lint` — both must pass
4. Open a PR against `main` using the PR template
5. A maintainer will review within 3 business days

## Branch Convention

| Prefix | Use |
|---|---|
| `feat/` | New feature |
| `fix/` | Bug fix |
| `chore/` | Tooling, deps, CI |
| `docs/` | Documentation only |
| `test/` | Test-only changes |
| `refactor/` | No behavior change |

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(query): add sparse search mode to streaming endpoint
fix(auth): prevent timing attack in password comparison
chore(deps): upgrade langfuse to 2.1.0
```

## What We Accept

✅ Bug fixes with a failing test that proves the fix  
✅ Performance improvements with benchmarks  
✅ New test coverage for untested paths  
✅ Documentation improvements  
✅ Security fixes (report via SECURITY.md first)

❌ New AI models or algorithms without prior discussion  
❌ Architecture changes (open an issue first)  
❌ Frontend redesign (open a discussion first)

## Questions

Open a GitHub Discussion for questions that don't fit an issue.
