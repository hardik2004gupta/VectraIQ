# CLAUDE.md — VectraIQ (enterprise-level-rag)

> This file provides Claude Code with full project context.  
> Read this before touching any file in this repository.

---

## Project Identity

- **Current name:** enterprise-level-rag  
- **Planned name:** VectraIQ  
- **Description:** Production-grade AI Knowledge Platform — Kubernetes IT-Operations Copilot with Hybrid RAG, Text2SQL, Intelligent Routing, Enterprise Security, and multi-tier caching.  
- **Python version:** 3.12  
- **Package manager:** `uv`

---

## Tech Stack

| Layer | Technology |
|---|---|
| Web framework | FastAPI 0.115+ |
| AI orchestration | LangGraph (state machine + PostgreSQL checkpointing) |
| LLM + embeddings | OpenAI (gpt-4o answer, gpt-4o-mini grader, text-embedding-3-small) |
| Vector store | Qdrant (dense cosine search) |
| Sparse search | scikit-learn TF-IDF (in-process) |
| Relational DB | PostgreSQL 16 (psycopg2 + psycopg v3 for LangGraph) |
| Cache | Upstash Redis (HTTP) with in-memory fallback |
| Web search fallback | Tavily API |
| Reranker | sentence-transformers CrossEncoder (local) or Voyage API |
| Security scanning | llm-guard |
| Document parsing | Docling (PDF, DOCX, HTML, TXT) |
| Frontend | Streamlit (developer test harness only) |
| Storage abstraction | Local filesystem or AWS S3 |

---

## Repository Layout

```
app/
  api/           # FastAPI routers: admin.py, auth.py, query.py
  core/          # LangGraph: graph.py (state machine), state.py (GraphState)
  middleware/    # auth.py (JWT), rate_limiter.py (Redis sliding window)
  security/      # 9 security layers (see Security section below)
  services/      # All AI pipeline services (see Services section)
  storage/       # StorageBackend abstraction (local/S3)
  config.py      # Pydantic Settings (reads .env)
  main.py        # FastAPI app factory
  models.py      # Pydantic request/response models
eval/            # Evaluation harness (RAGAS, 40 golden questions)
notebooks/       # Research/exploration notebooks (not production)
scripts/
  seed_db.py     # DB migrations + document ingestion
  serve.py       # Uvicorn launcher
  streamlit_app.py  # Developer UI (1337 lines)
seed/
  docs/true_data/   # K8s documentation corpus (50+ files)
  docs/noisy_data/  # Noise corpus (populated by make seed-data)
  migrations/       # SQL: 001_create_users.sql, 003_seed_k8s_ops.sql
```

---

## Architecture Overview

### Request Flow

```
POST /query
  → JWT auth → rate limit → token budget → input restructure
  → llm-guard input scan → PII redaction (input)
  → LangGraph graph.invoke()
      → route_intent (LLM classifies: sql / rag / hybrid)
      → [rag]    → generate_answer → run_rag()
      → [sql]    → generate_sql → interrupt() → approve → execute → generate_answer
      → [hybrid] → retrieve_rag → generate_sql → interrupt() → execute → generate_answer
  → PII redaction (output) → consume token budget
  → ChatResponse
```

### AI Pipeline Services

| Service | File | Purpose |
|---|---|---|
| Intent router | `services/router_service.py` | LLM classifies question → sql/rag/hybrid |
| RAG orchestrator | `services/rag_service.py` | Coordinates all retrieval + generation |
| Embedding | `services/embedding_service.py` | OpenAI embeddings with Redis cache |
| Vector store | `services/vector_store.py` | Qdrant dense/sparse/hybrid search |
| Sparse index | `services/sparse_vector_service.py` | TF-IDF + RRF fusion |
| HyDE | `services/hyde.py` | Hypothetical document embeddings |
| Reranker | `services/reranking.py` | CrossEncoder or Voyage reranking |
| CRAG | `services/crag.py` | Relevance grading + Tavily web fallback |
| Self-RAG | `services/self_reflective.py` | Answer quality reflection loop |
| Text2SQL | `services/sql_service.py` | Schema introspection + GPT-4o SQL gen |
| Cache | `services/query_cache_service.py` | 5-tier Redis+memory cache |
| Doc cache | `services/doc_cache_service.py` | Content-hash dedup for uploads |
| LLM | `services/llm_service.py` | OpenAI generate/generate_with_json |
| Web search | `services/web_search.py` | Tavily CRAG fallback |

### Security Layers (in order of execution)

1. Pydantic `field_validator` — regex injection pattern check
2. JWT bearer auth — `middleware/auth.py`
3. Rate limiting — sliding window per user (Redis)
4. Token budget — daily cap per user (Redis)
5. Input restructuring — tiktoken truncate/summarize
6. llm-guard input scan — PromptInjection + Toxicity + BanTopics
7. Content moderation (input) — PII redaction via llm-guard
8. Spotlighting — XML-tagged retrieved context with security preamble
9. Hardened system prompt — behavioral rules + domain restrictions
10. Content moderation (output) — PII redaction on answer

---

## Known Critical Issues (from AUDIT_REPORT.md)

**Read this before making any changes.**

1. **`local_storage.py` is empty** — 1-line file, not implemented. `DocCacheService` with `storage_backend=local` will fail. Use `storage_backend=s3` or implement local backend.

2. **`psycopg[binary]` (v3) is NOT in `pyproject.toml`** — installed manually in `Dockerfile`. LangGraph checkpointer will fail if installed from `pyproject.toml` alone.

3. **`_build_sparse_index()` runs on every hybrid/sparse query** — scrolls 10,000 Qdrant documents + TF-IDF fit every single call. No caching. Major performance bottleneck.

4. **`Reranker()` is instantiated per request** — CrossEncoder model loaded from disk on each call. No module-level singleton.

5. **`/documents/upload` endpoint does not exist** — Streamlit UI calls it; FastAPI has no such route.

6. **Redis `cache.clear()` is a no-op** — Upstash SDK limitation. Only in-memory cache is cleared.

7. **SQL approval not user-scoped** — any authenticated user can resume any SQL thread via `/query/sql/execute`.

8. **Dual execution paths** — `rag_service.py` and LangGraph `graph.py` both implement intent routing, retrieval, and SQL generation independently. Changes to one may need to be mirrored in the other.

9. **`SQLService` instantiated multiple times** — `_schema_context` cache never hits because new instances are created per call in `rag_service.py`.

10. **`_DOCUMENT_HINTS` in `router_service.py`** contains ML paper terms (`elastic-cache`, `llada`, `gsm8k`, `humaneval`, `qkv`) that have nothing to do with Kubernetes — these are stale from a previous project.

---

## Development Commands

```bash
# One-time setup
make install          # uv venv + install all deps

# Sync deps
make sync             # uv sync --extra dev

# Database + document ingestion
make seed             # run migrations + seed users + ingest docs

# Run servers
make api              # FastAPI at :8000
make streamlit        # Streamlit UI at :8501

# Evaluation
make eval-baseline    # run naive profile
make eval-all         # run all features profile
make eval             # baseline + all + diff

# Code quality
make lint             # ruff check
make format           # ruff format
make test             # pytest (no tests exist yet)

# Docker
docker compose up     # Postgres + Qdrant + App
```

---

## Environment Variables (required)

Minimum to run locally:
```
OPENAI_API_KEY=...
QDRANT_URL=http://localhost:6333
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/adv_rag
UPSTASH_REDIS_URL=...       # optional; in-memory fallback used if absent
UPSTASH_REDIS_TOKEN=...
JWT_SECRET=...              # must be set; no startup validation yet
```

See `.env.example` for complete list with documentation.

---

## Psycopg Version Mixing

This project uses **two different Postgres drivers simultaneously**:

| Driver | Version | Used in |
|---|---|---|
| `psycopg2-binary` | v2 | `app/api/auth.py`, `app/api/admin.py`, `app/services/sql_service.py`, `scripts/seed_db.py` |
| `psycopg[binary]` | v3 | `app/core/graph.py` (LangGraph `PostgresSaver`) |

Both must be installed. `psycopg[binary]` (v3) is in `Dockerfile` but **not** in `pyproject.toml`. This is a known issue.

---

## Evaluation System

The evaluation harness in `eval/` measures RAG quality across 40 golden questions:

- **Golden questions:** `eval/seed_questions.yaml` — 40 Q&A pairs with expected sources, keywords, intent, and feature tags
- **Profiles:** `eval/profiles.py` — 7 profiles from `naive` (dense-only) to `all` (all features enabled)
- **Metrics:** RAGAS (faithfulness, context precision, context recall, answer relevancy) + forbidden keyword checks + source overlap
- **Output:** JSON files in `eval/results/` viewable in Streamlit eval dashboard tab

**Do not modify `eval/seed_questions.yaml` without running a full eval comparison.** These questions have validated expected behaviors.

---

## Project Phase

- **Phase 0 (current):** Read-only audit — `AUDIT_REPORT.md` generated  
- **Phase 1 (next):** Targeted bug fixes and critical refactors (see AUDIT_REPORT.md §19)  
- **Future:** VectraIQ rebrand, clean architecture, React frontend, SaaS deployment

---

## File Status Quick Reference

| File | Status |
|---|---|
| `app/storage/local_storage.py` | BROKEN (empty) |
| `app/security/output_validator.py` | UNWIRED (dead code) |
| `scripts/data_pipeline/` | MISSING (referenced by Makefile) |
| `tests/` | MISSING (referenced by pyproject.toml) |
| `seed/migrations/002_seed_ecommerce.sql` | MISSING (referenced by migration comment) |
| `/documents/upload` API endpoint | MISSING (called by Streamlit) |
