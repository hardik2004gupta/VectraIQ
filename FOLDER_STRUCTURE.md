# VectraIQ v2 — Folder Structure
**Version:** 2.0  
**Status:** Design Phase  

---

## Overview

VectraIQ v2 is organized as a monorepo. Two deployable applications (`web` and `api`) live under `apps/`. Shared code lives in `packages/`. Infrastructure configuration, scripts, and documentation are top-level.

The guiding rule: **a file lives in the most specific location possible.** Shared only when truly shared. Collocated by feature, not by file type.

---

## Complete Hierarchy

```
vectraiq/
│
├── apps/
│   ├── api/                          # FastAPI backend application
│   │   ├── src/
│   │   │   ├── api/                  # HTTP layer — routers, middleware, schemas
│   │   │   │   ├── v1/
│   │   │   │   │   ├── routers/
│   │   │   │   │   │   ├── auth.py         # POST /api/v1/auth/register, /login, /logout
│   │   │   │   │   │   ├── query.py        # POST /api/v1/query, /query/stream, /query/sql/execute
│   │   │   │   │   │   ├── documents.py    # POST /api/v1/documents/upload, GET /list, DELETE
│   │   │   │   │   │   ├── admin.py        # GET /api/v1/admin/health, /cache, /users
│   │   │   │   │   │   └── analytics.py    # GET /api/v1/analytics/usage, /queries
│   │   │   │   │   ├── schemas/
│   │   │   │   │   │   ├── auth.py         # LoginRequest, RegisterRequest, TokenResponse
│   │   │   │   │   │   ├── query.py        # QueryRequest, ChatResponse, StreamEvent
│   │   │   │   │   │   ├── documents.py    # UploadResponse, DocumentListItem
│   │   │   │   │   │   ├── admin.py        # HealthResponse, CacheStats
│   │   │   │   │   │   └── common.py       # ErrorResponse, PaginatedResponse
│   │   │   │   │   └── dependencies.py     # Shared FastAPI Depends: get_current_user, get_db
│   │   │   │   └── middleware/
│   │   │   │       ├── auth.py             # JWT Bearer extraction + user resolution
│   │   │   │       ├── rate_limiter.py     # Redis sliding-window rate limiting
│   │   │   │       ├── token_budget.py     # Per-user daily token cap
│   │   │   │       ├── cors.py             # CORS configuration
│   │   │   │       ├── logging.py          # Request/response structured logging
│   │   │   │       └── trace.py            # trace_id injection per request
│   │   │   │
│   │   │   ├── application/          # Use cases — orchestrate AI engine + repositories
│   │   │   │   ├── use_cases/
│   │   │   │   │   ├── query_use_case.py       # Route → Retrieve → Generate → Validate
│   │   │   │   │   ├── document_use_case.py    # Upload → Parse → Embed → Index
│   │   │   │   │   ├── auth_use_case.py        # Register, Login, token lifecycle
│   │   │   │   │   └── analytics_use_case.py   # Usage stats aggregation
│   │   │   │   ├── orchestrator.py             # LangGraph graph builder + singleton
│   │   │   │   └── dto/
│   │   │   │       ├── query_dto.py            # Internal data transfer objects
│   │   │   │       └── document_dto.py
│   │   │   │
│   │   │   ├── domain/               # Business entities and interfaces — no dependencies
│   │   │   │   ├── entities/
│   │   │   │   │   ├── user.py             # User entity (id, username, role, created_at)
│   │   │   │   │   ├── document.py         # Document entity (id, name, hash, status)
│   │   │   │   │   ├── chunk.py            # RetrievedChunk (text, source, score)
│   │   │   │   │   ├── query_result.py     # QueryResult (answer, sources, confidence, metadata)
│   │   │   │   │   └── conversation.py     # Conversation turn (question, answer, timestamp)
│   │   │   │   ├── repositories/           # Abstract interfaces (ports)
│   │   │   │   │   ├── user_repository.py
│   │   │   │   │   ├── document_repository.py
│   │   │   │   │   ├── vector_repository.py
│   │   │   │   │   ├── cache_repository.py
│   │   │   │   │   └── storage_repository.py
│   │   │   │   └── value_objects/
│   │   │   │       ├── intent.py           # Intent enum: RAG | SQL | HYBRID
│   │   │   │       ├── search_mode.py      # SearchMode enum: DENSE | SPARSE | HYBRID
│   │   │   │       └── query_flags.py      # QueryFlags dataclass (all feature toggles)
│   │   │   │
│   │   │   ├── infrastructure/       # Concrete implementations of repository interfaces
│   │   │   │   ├── db/
│   │   │   │   │   ├── connection.py       # psycopg v3 connection pool (singleton)
│   │   │   │   │   ├── migrations/         # SQL migration files
│   │   │   │   │   │   ├── 001_users.sql
│   │   │   │   │   │   ├── 002_documents.sql
│   │   │   │   │   │   ├── 003_conversations.sql
│   │   │   │   │   │   └── 004_k8s_ops_data.sql
│   │   │   │   │   ├── repositories/
│   │   │   │   │   │   ├── pg_user_repository.py
│   │   │   │   │   │   └── pg_document_repository.py
│   │   │   │   │   └── models.py           # SQLAlchemy-free raw SQL query builders
│   │   │   │   ├── vector/
│   │   │   │   │   └── qdrant_repository.py    # QdrantClient wrapper implementing VectorRepository
│   │   │   │   ├── cache/
│   │   │   │   │   ├── redis_repository.py     # Upstash Redis implementing CacheRepository
│   │   │   │   │   └── memory_repository.py    # In-memory LRU fallback
│   │   │   │   ├── storage/
│   │   │   │   │   ├── r2_storage.py           # Cloudflare R2 (S3-compatible)
│   │   │   │   │   └── local_storage.py        # Local filesystem (dev only)
│   │   │   │   └── providers/
│   │   │   │       ├── openai_provider.py      # LLM + embedding (OpenAI SDK)
│   │   │   │       ├── tavily_provider.py      # Web search
│   │   │   │       └── voyage_provider.py      # Voyage reranking API
│   │   │   │
│   │   │   ├── ai/                   # AI Engine — pure AI logic, no HTTP, no DB
│   │   │   │   ├── router/
│   │   │   │   │   ├── intent_classifier.py    # LLM intent: sql/rag/hybrid
│   │   │   │   │   └── keyword_router.py       # Fast keyword-based pre-classification
│   │   │   │   ├── retriever/
│   │   │   │   │   ├── dense_retriever.py      # Qdrant cosine similarity
│   │   │   │   │   ├── sparse_retriever.py     # TF-IDF singleton index
│   │   │   │   │   ├── hybrid_retriever.py     # Dense + Sparse + RRF fusion
│   │   │   │   │   └── hyde_retriever.py       # Hypothetical document embeddings
│   │   │   │   ├── reranker/
│   │   │   │   │   ├── base.py                 # Abstract Reranker interface
│   │   │   │   │   ├── cross_encoder.py        # sentence-transformers CrossEncoder singleton
│   │   │   │   │   └── voyage_reranker.py      # Voyage AI reranking
│   │   │   │   ├── generator/
│   │   │   │   │   ├── answer_generator.py     # OpenAI answer generation
│   │   │   │   │   └── sql_generator.py        # Schema-aware Text2SQL
│   │   │   │   ├── reasoner/
│   │   │   │   │   ├── crag.py                 # Corrective RAG + web fallback
│   │   │   │   │   └── self_rag.py             # Self-RAG reflection loop
│   │   │   │   ├── security/
│   │   │   │   │   ├── input_guard.py          # llm-guard input scanning
│   │   │   │   │   ├── output_guard.py         # llm-guard output scanning + PII redaction
│   │   │   │   │   ├── spotlighting.py         # XML context tagging
│   │   │   │   │   ├── input_restructuring.py  # Tiktoken truncate/summarize
│   │   │   │   │   └── system_prompt.py        # Hardened system prompt builder
│   │   │   │   ├── embedding/
│   │   │   │   │   └── embedding_service.py    # Cached embed_texts with batch support
│   │   │   │   └── sql/
│   │   │   │       ├── sql_validator.py        # SELECT-only enforcement (improved)
│   │   │   │       └── schema_inspector.py     # Postgres schema introspection (singleton)
│   │   │   │
│   │   │   ├── core/                 # Shared utilities — used by all layers
│   │   │   │   ├── config.py               # Pydantic Settings (all env vars, validated at startup)
│   │   │   │   ├── exceptions.py           # Typed exception hierarchy
│   │   │   │   ├── logging.py              # Loguru configuration
│   │   │   │   ├── security.py             # JWT create/verify, bcrypt hash
│   │   │   │   ├── pagination.py           # Cursor-based pagination helpers
│   │   │   │   └── startup.py              # Startup validation (secrets, connectivity checks)
│   │   │   │
│   │   │   └── main.py               # FastAPI app factory (lifespan events, router mounting)
│   │   │
│   │   ├── tests/
│   │   │   ├── unit/
│   │   │   │   ├── ai/                     # Unit tests for each AI module
│   │   │   │   ├── application/            # Use case unit tests with mocked repositories
│   │   │   │   └── core/                   # Config, security, logging
│   │   │   ├── integration/
│   │   │   │   ├── test_query_flow.py      # Full query pipeline with real services
│   │   │   │   ├── test_document_upload.py
│   │   │   │   └── test_sql_flow.py
│   │   │   ├── api/
│   │   │   │   ├── test_auth_endpoints.py
│   │   │   │   ├── test_query_endpoints.py
│   │   │   │   └── test_admin_endpoints.py
│   │   │   └── conftest.py                 # Fixtures: test DB, mock Redis, test client
│   │   │
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   └── uv.lock
│   │
│   └── web/                          # Next.js frontend application
│       ├── src/
│       │   ├── app/                  # Next.js 14 App Router
│       │   │   ├── (auth)/
│       │   │   │   ├── login/
│       │   │   │   │   └── page.tsx
│       │   │   │   └── register/
│       │   │   │       └── page.tsx
│       │   │   ├── (dashboard)/
│       │   │   │   ├── layout.tsx          # Dashboard shell with sidebar
│       │   │   │   ├── page.tsx            # Dashboard home (usage summary)
│       │   │   │   ├── chat/
│       │   │   │   │   ├── page.tsx        # Chat interface
│       │   │   │   │   └── [id]/page.tsx   # Individual conversation
│       │   │   │   ├── documents/
│       │   │   │   │   └── page.tsx        # Document management
│       │   │   │   ├── analytics/
│       │   │   │   │   └── page.tsx        # Usage analytics
│       │   │   │   └── settings/
│       │   │   │       └── page.tsx        # User + org settings
│       │   │   ├── (marketing)/
│       │   │   │   └── page.tsx            # Landing page
│       │   │   ├── layout.tsx              # Root layout
│       │   │   ├── globals.css
│       │   │   └── not-found.tsx
│       │   │
│       │   ├── components/
│       │   │   ├── ui/                     # shadcn/ui primitives (Button, Card, Input...)
│       │   │   ├── layout/
│       │   │   │   ├── Sidebar.tsx
│       │   │   │   ├── Header.tsx
│       │   │   │   └── MobileNav.tsx
│       │   │   ├── chat/
│       │   │   │   ├── ChatWindow.tsx      # Message list + scroll container
│       │   │   │   ├── MessageBubble.tsx   # User/AI message rendering
│       │   │   │   ├── QueryInput.tsx      # Textarea + feature toggles + submit
│       │   │   │   ├── FeatureToggles.tsx  # HyDE, Rerank, CRAG, Self-RAG toggles
│       │   │   │   ├── SourcesPanel.tsx    # Retrieved chunks viewer
│       │   │   │   ├── SqlApprovalCard.tsx # Human-in-the-loop SQL approval UI
│       │   │   │   └── StreamingDots.tsx   # Animated loading indicator
│       │   │   ├── documents/
│       │   │   │   ├── UploadZone.tsx      # Drag-and-drop file upload
│       │   │   │   ├── DocumentTable.tsx   # Paginated document list
│       │   │   │   └── ProcessingBadge.tsx # Upload status indicator
│       │   │   ├── analytics/
│       │   │   │   ├── UsageChart.tsx      # Queries per day line chart
│       │   │   │   ├── CacheStats.tsx      # Hit rate gauges
│       │   │   │   └── RouteBreakdown.tsx  # RAG/SQL/Hybrid pie chart
│       │   │   └── common/
│       │   │       ├── MarkdownRenderer.tsx
│       │   │       ├── CodeBlock.tsx
│       │   │       ├── ConfidenceBadge.tsx
│       │   │       ├── RouteBadge.tsx
│       │   │       └── ErrorBoundary.tsx
│       │   │
│       │   ├── hooks/
│       │   │   ├── useChat.ts              # Chat state + SSE streaming hook
│       │   │   ├── useDocuments.ts         # Document CRUD
│       │   │   ├── useAuth.ts              # Login, register, logout, token refresh
│       │   │   └── useAnalytics.ts
│       │   │
│       │   ├── lib/
│       │   │   ├── api-client.ts           # Typed fetch wrapper (all API calls)
│       │   │   ├── stream-parser.ts        # SSE event parser
│       │   │   ├── auth.ts                 # Token storage (httpOnly cookie via API route)
│       │   │   └── utils.ts                # cn(), formatDate(), etc.
│       │   │
│       │   ├── store/
│       │   │   ├── chat-store.ts           # Zustand: conversation history
│       │   │   └── ui-store.ts             # Zustand: sidebar, panel states
│       │   │
│       │   └── types/
│       │       ├── api.ts                  # TypeScript types matching backend schemas
│       │       └── chat.ts
│       │
│       ├── public/
│       │   ├── logo.svg
│       │   └── og-image.png
│       │
│       ├── next.config.ts
│       ├── tailwind.config.ts
│       ├── tsconfig.json
│       └── package.json
│
├── packages/                         # Shared code (future use)
│   └── types/                        # Shared TypeScript types (if type generation added)
│       └── package.json
│
├── eval/                             # Evaluation harness (kept from v1)
│   ├── invokers.py
│   ├── post_checks.py
│   ├── profiles.py
│   ├── ragas_adapter.py
│   ├── reporting.py
│   ├── run_ragas.py
│   ├── schema.py
│   └── seed_questions.yaml
│
├── infra/                            # Infrastructure as code
│   ├── docker/
│   │   ├── docker-compose.yml        # Full local stack (Postgres + Qdrant + API + Web)
│   │   ├── docker-compose.dev.yml    # Dev overrides (hot reload, no SSL)
│   │   └── docker-compose.prod.yml   # Production overrides
│   ├── railway/
│   │   └── railway.toml              # Railway deployment config
│   └── vercel/
│       └── vercel.json               # Vercel deployment config
│
├── seed/                             # Development seed data
│   ├── docs/
│   │   ├── true_data/               # K8s documentation corpus
│   │   └── noisy_data/              # Noise corpus
│   └── migrations/                  # Moved to apps/api/src/infrastructure/db/migrations/
│                                     # (this folder kept for legacy compatibility during migration)
│
├── scripts/                          # Utility scripts
│   ├── seed_db.py                    # DB migrations + user seeding
│   ├── ingest_docs.py                # Document ingestion (separated from seed_db)
│   ├── generate_eval_data.py         # Eval data generation
│   └── check_health.py               # Pre-flight connectivity check
│
├── docs/                             # Project documentation
│   ├── architecture/
│   │   ├── ARCHITECTURE_V2.md
│   │   ├── AI_ARCHITECTURE.md
│   │   └── DATA_FLOW.md
│   ├── api/
│   │   └── openapi.yaml              # Auto-generated from FastAPI
│   ├── deployment/
│   │   └── DEPLOYMENT_PLAN.md
│   └── guides/
│       ├── DEVELOPER_GUIDE.md
│       └── CONTRIBUTING.md
│
├── .github/
│   └── workflows/
│       ├── ci.yml                    # Lint, type check, test on PR
│       ├── deploy-api.yml            # Deploy API to Railway on main merge
│       └── deploy-web.yml            # Deploy web to Vercel on main merge
│
├── .env.example                      # Root env template
├── .gitignore
├── CLAUDE.md                         # Claude Code context file
├── AUDIT_REPORT.md                   # Phase 0 audit output
├── README.md
└── Makefile                          # Top-level commands
```

---

## Key Structural Decisions

### Why `apps/api/src/` not flat `app/`?

The `src/` layout is a Python best practice that prevents accidental import of development files. It also cleanly maps to clean architecture layers visible in the directory hierarchy.

### Why `domain/` has no dependencies?

The `domain/` directory contains only Python dataclasses, enums, and abstract base classes. Zero external imports. This makes domain objects testable in isolation with no mocking required.

### Why `ai/` is a sub-package of `src/`, not a separate package?

The AI modules are tightly coupled to the application's domain entities (they produce and consume `RetrievedChunk`, `QueryResult`, etc.). Separating them into an independent package would require either duplicating types or creating circular dependencies. They stay in `apps/api/src/ai/` and are tested independently.

### Why `eval/` stays at the root?

The evaluation harness is a standalone tool that tests the running API. It doesn't belong inside `apps/api/` (it's not part of the deployable application) and it runs against any deployment environment. Root level keeps it discoverable.

### Why monorepo instead of separate repos?

- One PR can change both API schema and frontend types simultaneously
- Unified CI pipeline catches integration breaks before merge
- Shared `Makefile` targets simplify developer experience
- Easy to enforce consistent tooling (ruff, mypy, prettier)

---

## File Count Estimate

| Directory | Approximate Files |
|---|---|
| `apps/api/src/` | ~60 Python files |
| `apps/api/tests/` | ~25 test files |
| `apps/web/src/` | ~40 TypeScript files |
| `eval/` | ~8 Python files (kept from v1) |
| `infra/` | ~5 config files |
| `scripts/` | ~4 Python files |
| `docs/` | ~8 markdown files |
| **Total** | **~150 files** |

Current v1 has ~30 Python files. v2 adds ~120 more from frontend, infrastructure-as-code, tests, and documentation.
