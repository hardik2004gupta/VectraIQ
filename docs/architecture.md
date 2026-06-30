# Architecture Guide

## Overview

VectraIQ is a production-grade AI Knowledge Platform built for Kubernetes IT operations. It combines Hybrid RAG, Text2SQL, intelligent intent routing, and a 10-layer security pipeline into a single FastAPI + LangGraph backend, served by a Next.js 15 frontend.

---

## Request Flow

```
POST /query
  → JWT auth → rate limit → token budget → tiktoken truncation
  → LLM-Guard input scan → PII redaction (input)
  → LangGraph graph.invoke()
      → route_intent  (LLM classifies: sql / rag / hybrid)
      → [rag]     → retrieve → rerank → grade → generate
      → [sql]     → generate_sql → interrupt() → approve → execute → generate
      → [hybrid]  → retrieve + generate_sql → interrupt() → execute → generate
  → PII redaction (output)
  → ChatResponse
```

---

## LangGraph State Machine

Seven nodes connected by conditional edges:

```
START → route_intent
route_intent → retrieve_rag          (intent == "rag")
route_intent → generate_sql          (intent == "sql")
route_intent → retrieve_rag          (intent == "hybrid", retrieval first)
retrieve_rag → generate_answer       (rag path)
generate_sql → interrupt             (awaits human approval)
interrupt    → execute_sql           (approved)
interrupt    → END                   (rejected)
execute_sql  → generate_answer
generate_answer → END
```

State is persisted in PostgreSQL via `PostgresSaver`. SQL queries pause at `interrupt()` until explicitly approved via `POST /query/sql/execute`.

---

## Hybrid RAG Pipeline

```
Query
  │
  ├─ HyDE (optional)         — generate hypothetical answer for better embedding
  │
  ├─ Dense retrieval         — Qdrant cosine similarity (text-embedding-3-small)
  ├─ Sparse retrieval        — TF-IDF with RRF fusion (module-level TTL cache)
  │
  ├─ Score fusion            — Reciprocal Rank Fusion
  ├─ Reranking (optional)    — CrossEncoder or Voyage API
  │
  ├─ CRAG grading (optional) — GPT-4o-mini relevance grade
  │     └─ below threshold → Tavily web search fallback
  │
  └─ Self-RAG (optional)     — quality reflection, retry if below threshold
```

---

## 10-Layer Security Pipeline

| Layer | Mechanism | Protects against |
|---|---|---|
| 1 | Pydantic `field_validator` regex | Obvious injection strings |
| 2 | JWT bearer auth | Unauthenticated access |
| 3 | Redis rate limiting (per user) | Abuse / DoS |
| 4 | Token budget (per user, daily) | Cost runaway |
| 5 | tiktoken truncation | Context overflow |
| 6 | LLM-Guard PromptInjection + Toxicity | ML-detected injection |
| 7 | PII redaction (input) | Data leakage in context |
| 8 | Spotlighting (XML tags) | Indirect prompt injection |
| 9 | Hardened system prompt | Domain drift, jailbreaks |
| 10 | PII redaction (output) | Credential leakage in answers |

---

## Caching Architecture

5-tier cache with Redis (Upstash) primary and in-memory LRU fallback:

| Tier | Key | TTL | Purpose |
|---|---|---|---|
| `embedding` | SHA256(text) | 7 days | Avoid re-embedding stable K8s docs |
| `rag_answer` | SHA256(question + flags) | 1 hour | Cache full RAG responses |
| `sql_gen` | SHA256(question) | 24 hours | Cache generated SQL |
| `sql_result` | SHA256(sql) | 15 minutes | Cache query results |
| `intent` | SHA256(question) | 24 hours | Cache intent classification |

---

## Package Structure

```
vectraiq/
├── api/            FastAPI routers (auth, query, admin)
├── ai/             AI services (RAG, embeddings, reranking, SQL, etc.)
├── cache/          Query cache + document dedup cache
├── core/           LangGraph graph + GraphState TypedDict
├── middleware/     Auth (JWT), rate limiter, request context, security headers
├── security/       LLM-Guard, PII, spotlighting, system prompt, token budget
├── storage/        StorageBackend abstraction (local + S3)
├── config.py       Pydantic Settings (reads .env)
├── exceptions.py   Typed exception hierarchy
├── logging_config.py  loguru + stdlib bridge + request_id
├── main.py         FastAPI app factory
├── models.py       Pydantic request/response models
└── observability.py  Metrics, Langfuse tracing, timed context managers
```

---

## Technology Choices

| Decision | Choice | Reason |
|---|---|---|
| LLM answer | GPT-4o | Best instruction-following for K8s ops answers |
| LLM grader | GPT-4o-mini | Sufficient for binary relevance grading; cheaper |
| Embeddings | text-embedding-3-small | Best price/performance for retrieval at this corpus size |
| Vector store | Qdrant | Native hybrid search, Rust performance, self-hostable |
| Sparse search | scikit-learn TF-IDF | No additional service required; acceptable for <100K docs |
| Orchestration | LangGraph | Stateful graph with native `interrupt()` for HIL approval |
| Checkpointing | PostgreSQL (psycopg v3) | Durable state, no extra infrastructure |
| App DB | psycopg2 (v2) | Synchronous, stable, well-tested |
| Cache | Upstash Redis | HTTP-based, no persistent connection required |
| Reranker | CrossEncoder / Voyage | CrossEncoder for self-hosted; Voyage for API-based |
