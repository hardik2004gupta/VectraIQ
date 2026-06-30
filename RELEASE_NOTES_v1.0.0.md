# VectraIQ v1.0.0 Release Notes

**Release Date:** 2026-06-30  
**Tag:** `v1.0.0`  
**Python:** 3.12  
**License:** MIT

---

## What is VectraIQ?

VectraIQ is a production-grade AI Knowledge Platform designed for Kubernetes IT-Operations teams. It turns your K8s documentation into an intelligent copilot that answers natural language questions, generates audited SQL, and falls back to live web search when the corpus doesn't have the answer.

---

## Highlights

### Hybrid RAG Pipeline
- **Dense + Sparse retrieval** — Qdrant cosine search fused with TF-IDF via Reciprocal Rank Fusion (RRF)
- **HyDE** — Hypothetical Document Embeddings generate richer query representations
- **CRAG** — Corrective RAG grades retrieved chunks and falls back to Tavily web search when relevance is low
- **Self-RAG** — Reflection loop verifies answer quality and re-retrieves if confidence is insufficient
- **Reranking** — CrossEncoder (local) or Voyage AI (remote) reranks top-k candidates before generation

### Text2SQL with Human-in-the-Loop
- GPT-4o generates SQL from natural language against your PostgreSQL schema
- LangGraph `interrupt()` pauses execution for human approval before any query runs
- Full schema introspection — no manual schema description required

### Intelligent Intent Routing
- LLM classifies every question as `rag`, `sql`, or `hybrid`
- Hybrid mode runs both pipelines and synthesizes a combined answer

### 10-Layer Security Pipeline
1. Pydantic field validator (regex injection patterns)
2. JWT HS256 bearer authentication
3. Redis sliding-window rate limiting (per user)
4. Daily token budget cap (per user)
5. tiktoken input truncation / summarization
6. llm-guard PromptInjection + Toxicity + BanTopics scan
7. PII redaction on input
8. XML spotlighting on retrieved context
9. Hardened system prompt with domain restrictions
10. PII redaction on output

### 5-Tier Query Cache
| Tier | Backend | TTL |
|---|---|---|
| Embedding | Redis + in-memory | 7 days |
| RAG answer | Redis + in-memory | 1 hour |
| SQL generation | Redis + in-memory | 24 hours |
| SQL result | Redis + in-memory | 15 minutes |
| Intent routing | Redis + in-memory | 24 hours |

Gracefully degrades to in-memory LRU when Redis (Upstash) is unavailable.

### Next.js 15 Frontend
- App Router with React 19 and TypeScript strict mode
- Real-time SSE streaming with per-stage status updates
- Chat history persisted to localStorage (survives page refresh)
- Analytics dashboard with cache hit rates and system health
- Accessible UI with ARIA labels and keyboard navigation throughout

### Production-Ready Infrastructure
- Non-root Docker container (`appuser`, UID 1001)
- Health checks on all services with `depends_on: condition: service_healthy`
- `restart: unless-stopped` on all Docker Compose services
- 7-job CI pipeline: lint → typecheck → test → frontend lint → frontend build → Docker build → security audit
- Structured JSON logging with request ID propagation

---

## What's New vs. Pre-Release

This is the first public release. The internal pre-release (tagged `2.0.0` in development) has been renumbered to `1.0.0` to follow SemVer convention for initial open-source releases.

Key improvements applied during the final release hardening cycle:

- **Security:** Container now runs as non-root user
- **Reliability:** All Docker services have restart policies and health-gate dependencies
- **Correctness:** Fixed deprecated `asyncio.get_event_loop()` call (Python 3.14 breakage)
- **UX:** Knowledge Base page now honestly communicates that upload is coming in v1.1 (previously showed a fake "indexed successfully" toast)
- **Frontend:** Chat history now persists across page refreshes via Zustand localStorage middleware
- **Theming:** All chart colors now use CSS design-system variables instead of hardcoded hex
- **CI:** Fixed `npm ci` failure caused by missing `package-lock.json`
- **Docker:** Comprehensive `.dockerignore` added; build context reduced significantly

---

## Getting Started

### Prerequisites
- Docker + Docker Compose
- OpenAI API key
- (Optional) Upstash Redis, Tavily API key, Voyage AI key

### Quick Start

```bash
# 1. Clone
git clone https://github.com/hardik2004gupta/VectraIQ.git
cd VectraIQ

# 2. Configure
cp .env.example .env
# Edit .env — set OPENAI_API_KEY, JWT_SECRET at minimum

# 3. Run
docker compose up
```

The API is available at `http://localhost:8000`. The Streamlit developer UI is available via `make streamlit`.

### Local Development

```bash
make install    # uv venv + install all deps
make seed       # run DB migrations + ingest K8s docs corpus
make api        # FastAPI at :8000
```

---

## Known Limitations

See [`KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md) for the full list. Top items:

- **Document upload API** — Not available in v1.0.0. Use `make seed` to ingest documents via CLI.
- **Sparse index performance** — TF-IDF index rebuilt on every hybrid query. v1.1 will cache this.
- **No test suite** — Backend unit tests are planned for v1.1.

---

## Roadmap

### v1.1 (planned)
- `POST /documents/upload` endpoint — full upload pipeline via API
- Persistent sparse index cache
- Backend unit test suite (target 60% coverage)
- Per-user SQL approval scoping
- Database connection pooling for auth routes

### v1.2 (planned)
- OpenTelemetry distributed tracing
- Redis cache invalidation by key prefix
- React frontend as the primary UI (replacing Streamlit)
- Multi-tenant workspace isolation

---

## Acknowledgements

Built with: FastAPI, LangGraph, Qdrant, OpenAI, sentence-transformers, llm-guard, Next.js 15, Zustand, TanStack Query, Tailwind CSS v4, Recharts, Framer Motion.

---

*VectraIQ is released under the MIT License.*
