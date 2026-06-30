# PERFORMANCE_REPORT.md — VectraIQ Phase 5

**Date:** 2026-06-30

---

## Summary

Phase 4 addressed the most critical performance regression: the sparse index being rebuilt on every query. Phase 5 documents the full performance picture, including latency characteristics, caching impact, and frontend bundle behavior.

---

## Backend Performance

### Sparse Index Caching (Phase 4 Fix — TD-007)

**Problem:** `_build_sparse_index()` scrolled all 10,000 Qdrant documents and re-fit a TF-IDF matrix on every sparse/hybrid query call. This added ~800ms–2s of overhead per request.

**Fix:** Module-level TTL cache with 30-minute expiry. The index is built once per process and reused. `invalidate_sparse_index()` is called after document upserts.

**Impact:**
- Cold (first query): ~1200ms (index build) + query latency
- Warm (subsequent): ~2ms (cache lookup) + query latency
- Expected improvement: **~1s per hybrid/sparse query**

### QdrantClient Singleton (Phase 4 Fix)

**Problem:** A new `QdrantClient` was instantiated on every vector search call, reconnecting to Qdrant each time.

**Fix:** Module-level singleton via `_get_qdrant_client()`.

**Impact:** Eliminates ~50–150ms TCP connection overhead per query.

### Multi-tier Query Cache

The 5-tier cache reduces LLM API costs and latency for repeated or similar queries:

| Tier | Key | TTL | Typical latency saved |
|---|---|---|---|
| `embedding` | hash(text) | 7 days | ~80ms (embedding API call) |
| `rag_answer` | hash(question + flags) | 1 hour | ~2,000ms (full pipeline) |
| `sql_gen` | hash(question) | 24 hours | ~1,000ms (SQL generation) |
| `sql_result` | hash(sql) | 15 min | ~50–500ms (DB query) |
| `intent_router` | hash(question) | 24 hours | ~200ms (intent classification) |

At steady state with a typical K8s ops team (repeated question patterns), cache hit rates of 40–70% are expected on `rag_answer` and `intent_router`.

### Estimated End-to-End Latencies (warm, no cache)

| Pipeline | P50 | P95 | Bottleneck |
|---|---|---|---|
| RAG (dense, no rerank) | ~1.8s | ~3.5s | OpenAI generate |
| RAG (hybrid + rerank) | ~2.5s | ~4.5s | CrossEncoder rerank |
| RAG (HyDE + hybrid + rerank) | ~3.5s | ~6s | HyDE generation + rerank |
| RAG (with CRAG web fallback) | ~4–8s | ~12s | Tavily API |
| SQL generation (until interrupt) | ~1s | ~2s | GPT-4o SQL gen |
| SQL + execute (approved) | ~1.5s | ~3s | DB query + generate |

*Estimates based on typical GPT-4o latencies as of 2026. Actual latencies depend on OpenAI load.*

### Startup Time

The app does not pre-warm the sparse index on startup. The first hybrid/sparse query in a session will pay the index-build cost (~800ms–2s depending on corpus size). This is acceptable for the current corpus size (50+ documents). If corpus grows to >10K documents, consider building the index during the lifespan startup event.

---

## Frontend Performance

### Bundle Analysis (Next.js 15)

**Automatic code splitting:** Each page route is a separate bundle. Heavy dependencies are isolated:
- `recharts` only loaded on `/analytics`
- `react-syntax-highlighter` only loaded when `MarkdownRenderer` is rendered
- `react-dropzone` only loaded on `/knowledge`

**TanStack Query staleTime:** Set to 30,000ms (30s) to prevent redundant health/stats fetches on every navigation.

**Font loading:** Google Fonts (Inter + JetBrains Mono) loaded with `next/font/google` which adds `display: swap` and `preload` links automatically.

### Rendering Strategy

All dashboard pages are Client Components (required for Zustand auth state). The landing page (`/`) contains no client state and renders statically.

**Auth guard:** Client-side redirect in `(dashboard)/layout.tsx`. This means the dashboard shell renders briefly before redirect. This is acceptable for an authenticated SaaS product.

### Known Frontend Performance Concerns

1. **`MarkdownRenderer` is not lazy-loaded.** For very long conversations with many code blocks, consider `React.lazy()` for the Prism SyntaxHighlighter import.

2. **Chat message list is not virtualized.** For sessions with >100 messages, consider `@tanstack/react-virtual` to avoid rendering all messages in the DOM.

3. **Recharts renders client-side only.** There is a brief layout shift on the Analytics page while charts mount. A server-rendered placeholder would improve CLS.

---

## Caching Architecture Diagram

```
Request
   │
   ├──► Intent Cache (TTL 24h) → hit → return cached intent
   │         ↓ miss
   ├──► Embedding Cache (TTL 7d) → hit → return cached vector
   │         ↓ miss
   ├──► [Qdrant search]
   │
   ├──► RAG Answer Cache (TTL 1h) → hit → return answer
   │         ↓ miss
   ├──► [OpenAI generate]
   │
   └──► [Response]
```

Redis (Upstash) is checked first. On miss, the in-memory LRU is checked. On miss, the full pipeline runs. Results are written to both Redis and in-memory.

---

## Optimization Recommendations (Post-Phase-5)

| Recommendation | Expected impact | Effort |
|---|---|---|
| Pre-warm sparse index on startup | Eliminate cold-start penalty | Low |
| `React.lazy` on MarkdownRenderer | Reduce initial chat bundle | Low |
| Virtualize chat message list | Handle 100+ message sessions | Medium |
| Connection pooling for psycopg2 | Reduce DB connection overhead under load | Medium |
| Streaming token-by-token from OpenAI | Dramatically improve perceived latency | High |
| Prometheus `/metrics` endpoint | Enable load-based autoscaling | Medium |
