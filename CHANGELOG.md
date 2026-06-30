# Changelog

All notable changes to VectraIQ are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).  
Versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] — 2026-06-30

### Added

**AI Pipeline**
- Hybrid RAG: dense (Qdrant cosine) + sparse (TF-IDF/RRF) + CrossEncoder/Voyage reranking
- HyDE (Hypothetical Document Embeddings) for improved retrieval recall
- CRAG (Corrective RAG): relevance grading + Tavily web search fallback
- Self-RAG: quality reflection loop with configurable retry threshold
- Text2SQL with human-in-the-loop approval via LangGraph `interrupt()`
- Intent routing: LLM classifies query → `rag` / `sql` / `hybrid`
- 5-tier query cache: embedding (7d), RAG answer (1h), SQL gen (24h), SQL result (15m), intent (24h)
- Sparse index TTL cache (30-minute rebuild window) eliminating per-query Qdrant scroll

**Backend**
- FastAPI 0.115+ application with `asynccontextmanager` lifespan
- LangGraph 7-node state machine with PostgreSQL checkpointing (`PostgresSaver`)
- `vectraiq/` Python package (Python 3.12, managed with `uv`)
- 10-layer security pipeline: Pydantic validators → JWT → rate limiting → token budget → tiktoken truncation → LLM-Guard (PromptInjection + Toxicity) → PII redaction → Spotlighting → hardened system prompt → output PII redaction
- JWT HS256 authentication with bcrypt (12 rounds) password hashing
- Redis sliding-window rate limiting per user and per IP (in-memory fallback when Redis absent)
- OWASP security response headers middleware
- Structured JSON logging via loguru with `request_id` context propagation
- SSE streaming endpoint (`POST /query/stream`) with real-time pipeline status events
- Optional Langfuse tracing (feature-flagged, zero overhead when disabled)
- Health endpoint returning 503 when critical services are down
- Custom exception hierarchy with typed HTTP status codes and error codes

**Frontend**
- Next.js 15 App Router with React 19 and TypeScript
- Tailwind CSS v4 dark-first design system (Inter + JetBrains Mono)
- Framer Motion animations including shared layout sidebar indicator
- Zustand (auth + chat state) + TanStack Query (server state)
- SSE client via `ReadableStream` async generator (supports POST + auth headers)
- Pages: Landing, Login, Register, Dashboard, AI Chat, Knowledge Base, Analytics, Settings
- SQL approval card with Approve/Cancel flow
- Markdown rendering with syntax highlighting in chat

**Infrastructure**
- Docker Compose with PostgreSQL 16, Qdrant v1.17.0, and app service with healthchecks
- 7-job GitHub Actions CI pipeline: lint, typecheck, tests, frontend build, Docker build, security scan, gate
- Release pipeline: Docker image to GHCR + GitHub Release on version tags
- RAGAS evaluation harness with 40 golden Kubernetes Q&A pairs across 7 feature profiles

**Documentation**
- `README.md` with badges, architecture diagram, quick start, API reference
- `CONTRIBUTING.md`, `SECURITY.md`, `LICENSE` (MIT)
- `.github/` issue templates, PR template, CI/CD workflows

### Known Limitations

- `/documents/upload` API endpoint not yet implemented (UI shows simulated upload; use `make seed` to ingest documents via CLI)
- SQL approval is not scoped to the requesting user (any authenticated user can resume any SQL thread)
- Redis `cache.clear()` clears in-memory cache only; remote Upstash entries expire by TTL
- Database connections are not pooled in `auth.py` (acceptable for low-concurrency deployments)
- Container runs as root (non-root user is a planned hardening step)

---

## [0.1.0] — 2026-01-01 (internal)

Initial prototype with basic dense RAG, FastAPI, and Streamlit frontend.
