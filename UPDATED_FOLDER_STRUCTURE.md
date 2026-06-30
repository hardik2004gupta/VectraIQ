# UPDATED_FOLDER_STRUCTURE.md — VectraIQ Phase 2

Current repository layout after Phase 2 restructuring.

```
enterprise-level-rag/
│
├── vectraiq/                        ← NEW authoritative Python package
│   ├── __init__.py                  # __version__ = "2.0.0"
│   ├── config.py                    # Pydantic Settings (vanna fields removed)
│   ├── models.py                    # Request/response models (deduped validators)
│   ├── main.py                      # FastAPI app factory
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── auth.py                  # /auth/register, /auth/login
│   │   ├── query.py                 # /query, /query/sql/execute
│   │   └── admin.py                 # /admin/health, cache stats/clear
│   │
│   ├── ai/                          ← all AI pipeline services
│   │   ├── llm_service.py           # OpenAI wrapper (module-level client)
│   │   ├── embedding_service.py     # text-embedding-3-small + Redis cache
│   │   ├── sparse_vector_service.py # TF-IDF index + RRF fusion
│   │   ├── vector_store.py          # Qdrant dense/sparse/hybrid search
│   │   ├── reranking.py             # CrossEncoder / Voyage reranker
│   │   ├── web_search.py            # Tavily search
│   │   ├── crag.py                  # CRAG (relevance grading + web fallback)
│   │   ├── hyde.py                  # HyDE retriever
│   │   ├── self_reflective.py       # Self-RAG reflection loop
│   │   ├── router_service.py        # Intent classification (sql/rag/hybrid)
│   │   ├── sql_service.py           # Text2SQL + schema introspection
│   │   ├── document_processor.py   # Docling PDF/DOCX/HTML/TXT ingestion
│   │   └── rag_service.py           # Full RAG orchestration
│   │
│   ├── cache/
│   │   ├── query_cache.py           # 5-tier Redis+memory cache (module singleton)
│   │   └── doc_cache.py             # Content-hash document deduplication
│   │
│   ├── security/
│   │   ├── __init__.py
│   │   ├── input_restructuring.py   # truncate_to_token_limit() (tiktoken)
│   │   ├── input_guard.py           # llm-guard input scan
│   │   ├── content_moderation.py    # PII redaction (email, phone, card — NOT IPs)
│   │   ├── output_validator.py      # Output quality validation
│   │   ├── spotlighting.py          # XML-tagged retrieved context
│   │   ├── system_prompt.py         # Hardened K8s SRE system prompt
│   │   └── token_budget.py          # Daily token cap per user (Redis)
│   │
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── auth.py                  # JWT HS256, bcrypt
│   │   └── rate_limiter.py          # Sliding window rate limit (Redis)
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── state.py                 # GraphState TypedDict (22 fields)
│   │   └── graph.py                 # LangGraph 7-node state machine
│   │
│   └── storage/
│       ├── __init__.py
│       ├── backend.py               # Abstract StorageBackend + factory
│       ├── local.py                 # LocalStorage (FIXED — was empty)
│       └── s3.py                    # S3Storage (boto3)
│
├── app/                             ← PRESERVED original package (safety net)
│   ├── api/
│   ├── core/
│   ├── middleware/
│   ├── security/
│   ├── services/
│   ├── storage/
│   ├── config.py
│   ├── main.py
│   └── models.py
│
├── eval/                            ← RAGAS evaluation harness
│   ├── invokers.py                  # Updated: vectraiq imports
│   ├── ragas_adapter.py             # Updated: vectraiq imports
│   ├── profiles.py
│   ├── run_ragas.py
│   ├── diff.py
│   ├── seed_questions.yaml          # 40 golden Q&A pairs
│   └── results/                     # JSON eval outputs
│
├── scripts/
│   ├── serve.py                     # Updated: vectraiq.main:app
│   ├── seed_db.py                   # Updated: vectraiq imports
│   └── streamlit_app.py             # Developer UI (unchanged)
│
├── seed/
│   ├── docs/
│   │   ├── true_data/               # K8s documentation corpus
│   │   └── noisy_data/              # Noise corpus
│   └── migrations/
│       ├── 001_create_users.sql
│       └── 003_seed_k8s_ops.sql
│
├── notebooks/                       # Research notebooks (not production)
│
├── docker-compose.yml               # Postgres + Qdrant + App
├── Dockerfile                       # App image
├── Makefile                         # Updated: vectraiq.main:app
├── pyproject.toml                   # Updated: name=vectraiq, packages=["vectraiq"]
├── .env.example
│
├── AUDIT_REPORT.md                  # Phase 0 — full repository audit
├── CLAUDE.md                        # Project context for Claude Code
├── ARCHITECTURE_V2.md               # Phase 1 — target architecture
├── FOLDER_STRUCTURE.md              # Phase 1 — target folder structure
├── BACKEND_BLUEPRINT.md             # Phase 1 — backend blueprint
├── AI_ARCHITECTURE.md               # Phase 1 — AI pipeline architecture
├── FRONTEND_BLUEPRINT.md            # Phase 1 — frontend blueprint
├── DEPLOYMENT_PLAN.md               # Phase 1 — deployment plan
├── FILE_MIGRATION_MAP.md            # Phase 1 — migration mapping
├── IMPLEMENTATION_ROADMAP.md        # Phase 1 — implementation roadmap
├── RISK_ANALYSIS.md                 # Phase 1 — risk analysis
├── RESTRUCTURE_REPORT.md            # Phase 2 — this restructure (summary)
├── MIGRATION_LOG.md                 # Phase 2 — file-by-file migration log
├── UPDATED_FOLDER_STRUCTURE.md      # Phase 2 — this file
└── CHANGELOG_PHASE2.md              # Phase 2 — changelog
```

---

## Import Path Reference

| Old (app/) | New (vectraiq/) |
|---|---|
| `from app.config import settings` | `from vectraiq.config import settings` |
| `from app.models import ...` | `from vectraiq.models import ...` |
| `from app.services.rag_service import run_rag` | `from vectraiq.ai.rag_service import run_rag` |
| `from app.services.query_cache_service import query_cache` | `from vectraiq.cache.query_cache import query_cache` |
| `from app.services.doc_cache_service import ...` | `from vectraiq.cache.doc_cache import ...` |
| `from app.storage.storage_backend import ...` | `from vectraiq.storage.backend import ...` |
| `from app.storage.local_storage import LocalStorage` | `from vectraiq.storage.local import LocalStorage` |
| `from app.storage.s3_storage import S3Storage` | `from vectraiq.storage.s3 import S3Storage` |
| `from app.security.input_restructuring import summarize_text` | `from vectraiq.security.input_restructuring import truncate_to_token_limit` |
| `from app.middleware.auth import ...` | `from vectraiq.middleware.auth import ...` |
| `from app.core.graph import graph` | `from vectraiq.core.graph import graph` |
| `from app.api import auth, query, admin` | `from vectraiq.api import auth, query, admin` |
