# VectraIQ v2 — Architecture Design
**Version:** 2.0  
**Status:** Design Phase (Phase 1 Planning)  
**Date:** 2026-06-30  

---

## Vision

VectraIQ is an Enterprise AI Knowledge Platform that enables teams to query their documents and operational databases using natural language. It combines Hybrid RAG, Text2SQL, intelligent routing, enterprise security, and a polished SaaS frontend into a single cohesive product.

---

## Guiding Principles

1. **Separation of concerns** — every layer has one reason to change
2. **Fail loudly at startup** — misconfiguration is caught before a request arrives
3. **Observable by default** — every component emits structured logs, metrics, and traces
4. **Stateless where possible** — horizontal scaling without sticky sessions
5. **AI features are optional** — the system degrades gracefully when features are disabled
6. **Security is not a layer — it is the environment** — every boundary is authenticated and validated

---

## Layer Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        PRESENTATION LAYER                        │
│                                                                   │
│   ┌─────────────────────────┐   ┌──────────────────────────┐    │
│   │     Next.js Web App      │   │    Swagger / ReDoc UI    │    │
│   │  (Vercel — Edge CDN)     │   │   (FastAPI auto-gen)     │    │
│   └────────────┬────────────┘   └──────────────────────────┘    │
└────────────────┼────────────────────────────────────────────────┘
                 │ HTTPS + Bearer JWT
┌────────────────▼────────────────────────────────────────────────┐
│                          API GATEWAY LAYER                        │
│                                                                   │
│   ┌────────────────────────────────────────────────────────┐    │
│   │                  FastAPI Application                    │    │
│   │                                                         │    │
│   │  /api/v1/auth      /api/v1/query     /api/v1/documents │    │
│   │  /api/v1/admin     /api/v1/health    /api/v1/analytics │    │
│   │                                                         │    │
│   │  Middleware: Auth → Rate Limit → Token Budget           │    │
│   │             → Input Validation → Security Scan          │    │
│   └────────────────────────────┬───────────────────────────┘    │
└────────────────────────────────┼────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────┐
│                       APPLICATION LAYER                           │
│                                                                   │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│   │ Query Use     │  │ Document Use  │  │ Analytics Use Case   │ │
│   │ Cases         │  │ Cases         │  │                      │ │
│   └──────┬───────┘  └──────┬───────┘  └──────────────────────┘ │
│          │                  │                                      │
│   ┌──────▼──────────────────▼──────────────────────────────┐    │
│   │                   AI Orchestrator                        │    │
│   │            (LangGraph State Machine)                     │    │
│   └────────────────────────────────────────────────────────┘    │
└────────────────────────────────┼────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────┐
│                          AI ENGINE LAYER                          │
│                                                                   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │  Router  │ │Retriever │ │ Reasoner │ │Generator │           │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │ Validator│ │  Cache   │ │ Security │ │Evaluator │           │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘           │
└────────────────────────────────┼────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────┐
│                       INFRASTRUCTURE LAYER                        │
│                                                                   │
│  ┌────────────┐ ┌─────────────┐ ┌──────────────┐ ┌──────────┐  │
│  │  Postgres  │ │   Qdrant    │ │ Upstash Redis│ │  R2/S3   │  │
│  │  (Neon)    │ │   Cloud     │ │              │ │ Storage  │  │
│  └────────────┘ └─────────────┘ └──────────────┘ └──────────┘  │
│                                                                   │
│  ┌────────────┐ ┌─────────────┐ ┌──────────────┐               │
│  │  OpenAI    │ │   Tavily    │ │ Voyage AI    │               │
│  │    API     │ │   Search    │ │  Reranker    │               │
│  └────────────┘ └─────────────┘ └──────────────┘               │
└─────────────────────────────────────────────────────────────────┘
```

---

## Layer Responsibilities

### 1. Presentation Layer

**What it is:** The user-facing interface. Stateless. Deployed to Vercel CDN.

**Responsibilities:**
- Render the VectraIQ SaaS UI (Next.js 14 App Router)
- Handle authentication state (JWT in httpOnly cookie or secure localStorage)
- Stream LLM responses via Server-Sent Events
- Show document management, chat history, analytics, and settings
- No business logic — all decisions made by the API

**Technology:** Next.js 14 (App Router), TypeScript, Tailwind CSS, shadcn/ui, Framer Motion, Zustand (state), React Query (server state)

**Does NOT do:**
- No direct database access
- No LLM calls
- No file processing
- No security decisions

---

### 2. API Gateway Layer

**What it is:** The single entry point for all client requests. Handles authentication, authorization, rate limiting, and request routing.

**Responsibilities:**
- JWT authentication on all protected routes
- Input validation (Pydantic models + security validators)
- Rate limiting (per-user sliding window via Redis)
- Daily token budget enforcement
- Request routing to application use cases
- Response serialization
- OpenAPI schema generation
- Health checks and readiness probes

**Technology:** FastAPI 0.115+, Python 3.12, Pydantic v2, uvicorn

**Does NOT do:**
- No AI logic
- No direct database queries (except auth)
- No file storage

**API versioning:** All routes prefixed with `/api/v1/`

---

### 3. Application Layer

**What it is:** The orchestration layer. Coordinates use cases by calling into the AI Engine and Infrastructure. Contains all business logic.

**Responsibilities:**
- Define use cases as clean Python classes (`QueryUseCase`, `DocumentUseCase`, `AnalyticsUseCase`)
- Coordinate between the AI Engine and data repositories
- Own the LangGraph orchestrator instance
- Manage conversation/session state
- Transform domain objects to API response schemas
- Handle caching policy (what to cache, for how long)

**Technology:** Pure Python classes, LangGraph, domain models

**Does NOT do:**
- No HTTP concerns
- No database queries (delegates to repositories)
- No direct external API calls (delegates to AI modules)

---

### 4. AI Engine Layer

**What it is:** A collection of independent, composable AI modules. Each module has a single responsibility and a typed interface.

**Responsibilities:**
- Intent routing (LLM classification)
- Document retrieval (dense, sparse, hybrid, HyDE)
- Context reranking (CrossEncoder, Voyage)
- Answer generation (OpenAI)
- Self-reflection (Self-RAG loop)
- CRAG evaluation and web fallback
- Text2SQL generation and validation
- Security scanning (llm-guard)
- Embedding with caching

**Technology:** Python, OpenAI SDK, sentence-transformers, scikit-learn, Qdrant client, Tavily, llm-guard

**Does NOT do:**
- No HTTP handling
- No database connections (uses repository interfaces)
- No business logic — pure AI functions

---

### 5. Infrastructure Layer

**What it is:** All external dependencies, wrapped in repository interfaces. The application layer depends on abstractions, not concrete implementations.

**Responsibilities:**
- `VectorRepository` — Qdrant operations (upsert, search, scroll)
- `DocumentRepository` — Postgres document metadata
- `UserRepository` — Postgres user management
- `CacheRepository` — Upstash Redis operations
- `StorageRepository` — Cloudflare R2 / S3 file operations
- `LLMProvider` — OpenAI API (swappable)
- `EmbeddingProvider` — OpenAI embeddings (swappable)
- `WebSearchProvider` — Tavily (swappable)
- `RerankProvider` — Voyage / local CrossEncoder (swappable)

**Technology:** psycopg (v3 only), qdrant-client, upstash-redis, boto3/S3-compatible, openai, tavily-python, voyageai, sentence-transformers

**Pattern:** Repository pattern with dependency injection. Each repository implements an abstract interface. Test doubles can be injected.

---

## Cross-Cutting Concerns

### Authentication & Authorization

- JWT (HS256, configurable expiry)
- Role-based: `user` | `admin` | `superadmin`
- Admin routes require `is_admin=True` claim in JWT
- No API key auth in v2 (future: API key tier for programmatic access)

### Observability

- **Structured logging:** loguru with JSON format in production, human-readable in dev
- **Request tracing:** each request gets a `trace_id` propagated through all layers
- **Metrics:** cache hit rates, LLM latency, retrieval scores exposed at `/api/v1/metrics`
- **Error tracking:** Sentry integration (optional, via env var)

### Security

All security decisions happen at the API layer before any AI processing:
1. JWT validation
2. Rate limiting
3. Token budget check
4. Input token count and truncation
5. llm-guard input scan
6. PII redaction on input

Post-AI processing:
7. llm-guard output scan
8. PII redaction on output
9. Schema validation of response

### Caching Strategy

Five independent Redis namespaces with SHA-256 content-hashed keys:

| Namespace | TTL | Scope |
|---|---|---|
| `embedding:v2` | 7 days | Per text content |
| `intent:v2` | 24 hours | Per question |
| `rag_answer:v2` | 1 hour | Per question + flags |
| `sql_gen:v2` | 24 hours | Per question |
| `sql_result:v2` | 15 min | Per SQL text |

Cache is write-through with Redis primary, in-memory LRU fallback (max 500 entries).

### Streaming

The `/api/v1/query/stream` endpoint returns Server-Sent Events (SSE). The AI engine yields tokens as they arrive from OpenAI. The frontend consumes the stream and renders progressively.

Non-streaming `/api/v1/query` returns a complete `ChatResponse` for backwards compatibility.

---

## Architecture Decision Records (ADRs)

### ADR-001: Remove Vanna, use custom Text2SQL

**Decision:** Keep the custom schema-introspection Text2SQL approach from v1, but improve it with few-shot examples stored in Postgres.  
**Reason:** Vanna is unused and adds ~50MB to the image. The custom approach is simpler and gives us full control.

### ADR-002: Unify execution path — rag_service is the single source of truth

**Decision:** Remove the duplicate routing/retrieval logic from `graph.py`. The LangGraph graph only handles state transitions and the SQL approval interrupt. All AI work goes through the AI Engine modules.  
**Reason:** Dual execution paths cause maintenance drift and double intent classification.

### ADR-003: psycopg v3 everywhere

**Decision:** Replace all psycopg2 usage with psycopg v3.  
**Reason:** psycopg v3 supports async natively, has better connection pooling, and is the current standard. Mixing v2 and v3 is a maintenance hazard.

### ADR-004: Singleton AI module instances

**Decision:** All expensive AI modules (CrossEncoder, SparseIndex, SQLService) are singleton instances initialized at startup.  
**Reason:** Eliminates cold-start latency and repeated model loading per request.

### ADR-005: Sparse index with background refresh

**Decision:** TF-IDF sparse index built once at startup and refreshed in a background thread after document upserts.  
**Reason:** Rebuilding on every query is the #1 performance bottleneck. Singleton with stale-while-revalidate is the correct pattern.

### ADR-006: API versioning from day one

**Decision:** All routes are prefixed `/api/v1/`.  
**Reason:** VectraIQ is a SaaS product. Version prefix allows breaking changes without breaking existing integrations.

### ADR-007: Monorepo with apps/ and packages/

**Decision:** Adopt a monorepo structure with separate apps (web, api) and shared packages.  
**Reason:** Enables type sharing between frontend and backend, unified CI, and clean separation of deployment units.
