# PERFORMANCE_REVIEW.md — VectraIQ Phase 3.5

**Audit date:** 2026-06-30  
**Method:** Static analysis of service code (no profiling data; all latency estimates based on operation types)

---

## Critical Performance Issues

### P0 — `_build_sparse_index()` Called on Every Hybrid/Sparse Query

**File:** `vectraiq/ai/vector_store.py`  
**Severity:** CRITICAL — production-blocking at any meaningful load

**What happens:**
```python
def _build_sparse_index() -> SparseVectorIndex:
    # 1. Scrolls ALL documents from Qdrant (limit=10000)
    all_points, _ = client.scroll(collection_name=..., limit=10000, with_payload=True, with_vectors=False)
    # 2. Extracts text from every payload
    documents = [p.payload.get("text", "") for p in all_points]
    # 3. Fits a new TF-IDF model from scratch
    sparse_index = SparseVectorIndex()
    sparse_index.fit(documents)  # TfidfVectorizer.fit_transform()
    return sparse_index

def sparse_search(query_text: str, top_k: int = 5):
    sparse_index = _build_sparse_index()  # CALLED ON EVERY sparse_search()
    return sparse_index.search(query_text, top_k=top_k)

def hybrid_search(query_embedding, query_text, top_k=5, ...):
    dense_results = search(...)             # Qdrant search
    sparse_index = _build_sparse_index()   # CALLED AGAIN in same hybrid_search()
    sparse_results = sparse_index.search(...)
    return fuse_rrf(...)
```

**Operations per sparse/hybrid query:**
1. HTTP round-trip to Qdrant to scroll 10,000 documents — **~500ms–5,000ms** depending on payload size
2. Deserialize 10,000 Qdrant point payloads
3. `TfidfVectorizer.fit_transform()` on 10,000 documents — **~500ms–2,000ms** for typical K8s doc sizes
4. Cosine similarity between query vector and 10,000 document vectors — **~100ms**

**Total overhead per hybrid query:** 1,000ms–7,000ms of pure infrastructure work that is identical on every single call.

In `hybrid_search()`, `_build_sparse_index()` appears to be called TWICE if tracing the call chain (once in `sparse_search()` if called independently, once in `hybrid_search()` — depends on whether `hybrid_search` calls `sparse_search` or `_build_sparse_index` directly). Worst case: 2× the above overhead.

**Fix:** Cache the `SparseVectorIndex` as a module-level variable. Rebuild only when the collection is updated (or on a TTL, e.g. every 30 minutes):

```python
_sparse_index: SparseVectorIndex | None = None
_sparse_index_built_at: float = 0.0
_SPARSE_INDEX_TTL_SECONDS = 1800  # 30 minutes

def _get_sparse_index() -> SparseVectorIndex:
    global _sparse_index, _sparse_index_built_at
    if _sparse_index is None or (time.time() - _sparse_index_built_at) > _SPARSE_INDEX_TTL_SECONDS:
        _sparse_index = _build_sparse_index()
        _sparse_index_built_at = time.time()
    return _sparse_index
```

**Expected improvement:** 1,000ms–7,000ms → ~0ms (after warmup) for all sparse/hybrid queries.

---

### P1 — `QdrantClient` Created on Every Vector Operation

**File:** `vectraiq/ai/vector_store.py`  
**Severity:** HIGH

```python
def get_client() -> QdrantClient:
    return QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)
```

This function is called inside `search()`, `hybrid_search()`, `sparse_search()`, `upsert_chunks()`, and `get_collection_info()`. A new `QdrantClient` object is created on every call. The `QdrantClient` constructor initializes an HTTP session (`httpx.Client`).

**Overhead:** HTTP session creation is ~20–50ms. For a hybrid search that calls `get_client()` twice (once for dense search, once for sparse scroll), this is 40–100ms of unnecessary overhead per request.

**Fix:** Module-level singleton:
```python
_qdrant_client: QdrantClient | None = None

def get_client() -> QdrantClient:
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None)
    return _qdrant_client
```

**Expected improvement:** ~50ms saved per vector operation.

---

### P1 — psycopg2 `connect()` Per Request

**Files:** `vectraiq/api/auth.py`, `vectraiq/api/admin.py`, `vectraiq/services/sql_service.py`  
**Severity:** HIGH

```python
# auth.py — per register/login call
conn = psycopg2.connect(settings.database_url)
try:
    cursor = conn.cursor()
    cursor.execute(...)
finally:
    conn.close()
```

Each auth request opens a new TCP connection to PostgreSQL, authenticates (MD5 or SCRAM), and closes it. PostgreSQL connection overhead: 20–100ms per connection (SSL adds ~10ms).

For a system under load (100 logins/minute), this creates 100 new PostgreSQL connections per minute, each short-lived.

**Fix:** Use a connection pool (`psycopg2.pool.ThreadedConnectionPool` or `psycopg_pool.ConnectionPool` for v3). A pool of 5–10 connections handles typical load with zero per-request connection overhead.

**Expected improvement:** 20–100ms saved per auth request.

---

### P1 — `graph.py` `retrieve_rag` Runs Full RAG Pipeline for Hybrid

**File:** `vectraiq/core/graph.py`  
**Severity:** HIGH — doubles LLM cost for hybrid queries going through LangGraph

```python
def retrieve_rag(state: GraphState) -> GraphState:
    response = run_rag(
        question=state["question"],
        flags={...}  # enables full pipeline: CRAG, reranking, etc.
    )
    # run_rag() performs: retrieve → rerank → grade → generate_answer (LLM call)
    # But only response.sources is used here:
    sources = response.sources
    spotlighted_context = build_spotlighted_context([...])
    return {**state, "spotlighted_context": spotlighted_context, "sources": sources}
```

`run_rag()` runs a **full RAG pipeline** including LLM generation. For the hybrid path, the generated answer from `run_rag()` is **discarded** — only `response.sources` is used for context spotlighting.

Then `generate_answer` node runs a separate `_generate_hybrid_answer()` which makes another LLM call.

**Wasted operations per hybrid query (LangGraph path):**
1. `retrieve_rag` → full `run_rag()` → 1 LLM call (discarded), 1 embedding call, Qdrant search, CRAG grading
2. `generate_sql_node` → 1 LLM call (SQL generation)
3. `execute_sql` → DB query
4. `_generate_hybrid_answer` → 1 LLM call (final answer)

**Total: 3 LLM calls, 1 embedding, 1 Qdrant search, 1 DB query** for a single hybrid question.

The correct implementation: `retrieve_rag` should call a retrieval-only function (e.g., the `_retrieve()` helper in `rag_service.py`) and NOT call `run_rag()`.

**Expected improvement:** 1 LLM call eliminated per hybrid query through LangGraph path. At ~$0.01 per LLM call and ~1,500ms latency, this is both a cost and UX improvement.

---

## High Performance Issues

### P2 — `tiktoken` Encoding Loaded Per `count_tokens()` Call

**File:** `vectraiq/security/input_restructuring.py`  
**Severity:** MEDIUM

```python
def count_tokens(text: str, model: str = "gpt-4o") -> int:
    enc = tiktoken.encoding_for_model(model)  # Loaded on every call
    return len(enc.encode(text))
```

`tiktoken.encoding_for_model()` loads the BPE vocabulary from disk on first call and caches it internally in tiktoken's module-level cache. The FIRST call is slow (~100ms for file load), subsequent calls hit tiktoken's internal cache and are fast (~1ms).

This is **not a critical bug** (tiktoken has its own internal cache), but the code pattern is misleading — it implies per-call cost when in reality tiktoken caches. No change needed, but worth noting for clarity.

---

### P2 — HyDE: Sequential LLM Calls

**File:** `vectraiq/ai/hyde.py`  
**Severity:** MEDIUM — HyDE is an opt-in feature, not default

```python
for i in range(self.num_hypotheses):  # default: 3
    response = self.llm_service.generate(...)  # sequential LLM call
    hypotheses.append(response["text"])
```

N=3 sequential LLM calls adds 3–8 seconds to query latency when HyDE is enabled. These N calls are independent and could be parallelized with `asyncio.gather()` or `concurrent.futures.ThreadPoolExecutor`.

**Expected improvement:** N×latency_per_call → max(latency_per_call) with parallelism. At 1,500ms per call: 4,500ms → 1,500ms.

---

### P2 — `_get_checkpointer()` Opens a Connection Without Pooling

**File:** `vectraiq/core/graph.py`  
**Severity:** MEDIUM

```python
def _get_checkpointer() -> PostgresSaver:
    conn = psycopg.connect(settings.database_url, autocommit=True)
    checkpointer = PostgresSaver(conn)
    checkpointer.setup()
    return checkpointer
```

A single `psycopg` v3 connection is created at module import time and held for the lifetime of the process. This connection:
- Has no reconnection logic (if the connection drops, the checkpointer fails permanently until restart)
- Is not pooled (single threaded access to checkpointing)
- Times out after PostgreSQL's `tcp_keepalives_idle` if idle

**Correct approach:** Use `psycopg_pool.ConnectionPool` or `AsyncConnectionPool` with reconnect enabled.

---

### P2 — Embedding Service: No Batch Parallelism with Cache Miss Handling

**File:** `vectraiq/ai/embedding_service.py`

```python
results = [None] * len(texts)
# ... fill from cache ...
uncached = [t for i, t in enumerate(texts) if results[i] is None]
if uncached:
    response = _openai_client.embeddings.create(input=uncached, model=settings.embedding_model)
    # ... fill results ...
return [r for r in results if r is not None]  # SUBTLE BUG
```

The final `return` filters out `None` values. If any slot is still `None` after the API call (network error, partial failure), the returned list will be SHORTER than the input. The caller at `vector_store.py:search()` uses the embedding directly:

```python
embedding = embed_text(question)
client.search(collection_name=..., query_vector=embedding, ...)
```

`embed_text()` returns a single vector — but `embed_texts()` with a length mismatch would silently drop entries and cause index misalignment in batch operations.

**Fix:** Either raise on `None` in results, or assert `len(output) == len(input)` before returning.

---

## Medium Performance Issues

### P3 — Self-RAG Sequential Retry Loop

**File:** `vectraiq/ai/self_reflective.py`

When Self-RAG is enabled and reflection score is low, the system regenerates the answer in a retry loop. The maximum iterations are bounded (typically 2-3), but each iteration is a sequential LLM call. Self-RAG is opt-in (default: `enable_self_reflective=False`), so this is only a concern when explicitly enabled.

---

### P3 — CRAG Grading: One LLM Call Per Chunk

**File:** `vectraiq/ai/crag.py`

The CRAG grading step calls `llm_service.generate_with_json()` once per chunk being graded. For `top_k=10`, this is 10 sequential LLM calls for grading alone. These are fast (gpt-4o-mini) but sequential.

**Estimated overhead:** 10 × 300ms = 3 seconds for relevance grading when CRAG is enabled with top_k=10.

---

## Performance Budget Estimate

For a single `hybrid` query with all features enabled (`enable_rerank=True`, `enable_hyde=True`, `enable_crag=True`):

| Operation | Estimated Time |
|---|---|
| Input restructuring (tiktoken) | ~5ms |
| llm-guard scan | ~200–500ms |
| PII redaction (input) | ~100–300ms |
| Intent classification (LLM) | ~300–600ms |
| HyDE (3 sequential LLM calls) | ~3,000–4,500ms |
| Embedding (4 vectors from HyDE + 1 query) | ~200ms |
| Qdrant dense search | ~50–200ms |
| TF-IDF index rebuild (CRITICAL BUG) | ~1,000–7,000ms |
| CRAG grading (10 chunks × 1 LLM) | ~2,000–4,000ms |
| Tavily web search (if triggered) | ~500–2,000ms |
| CrossEncoder reranking | ~100–500ms |
| SQL generation (LLM) | ~300–800ms |
| SQL execution (PostgreSQL) | ~50–500ms |
| Hybrid answer synthesis (LLM) | ~500–1,500ms |
| PII redaction (output) | ~100–300ms |
| **Total (worst case)** | **~8,000–22,000ms** |

Without the sparse index bug fix, hybrid queries are 5–30 seconds at minimum. With the fix (cached index), this drops to ~3–15 seconds — acceptable for an IT-ops copilot where users expect latency.

---

## Quick Wins (fixes that take <2 hours each)

| Fix | Time | Impact |
|---|---|---|
| Cache `_build_sparse_index()` as module-level singleton | 30 min | Eliminates 1–7s per hybrid/sparse query |
| Cache `QdrantClient` as module-level singleton | 15 min | Saves 50ms per vector operation |
| Fix `retrieve_rag` to call retrieval-only, not `run_rag()` | 1 hour | Eliminates 1 LLM call per hybrid query |
| Add psycopg2 connection pool | 2 hours | Eliminates 20–100ms per auth/SQL request |
| Parallelize HyDE LLM calls | 1 hour | Reduces HyDE from 3×latency to 1×latency |

These 5 changes collectively reduce worst-case hybrid query latency from ~22 seconds to ~8 seconds and typical latency from ~6 seconds to ~2 seconds.
