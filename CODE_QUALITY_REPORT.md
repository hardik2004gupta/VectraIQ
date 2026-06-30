# CODE_QUALITY_REPORT.md — VectraIQ Phase 3.5

**Audit date:** 2026-06-30  
**Scope:** vectraiq/ Python package  
**Focus:** Duplicate code, dead code, oversized functions, magic constants, inconsistencies

---

## 1. Duplicate Code

### 1A. Dual Execution Paths (CRITICAL)

The most significant quality issue in the codebase: two parallel implementations of the same logic.

**`vectraiq/ai/rag_service.py`** implements:
- Intent routing (`classify_intent()` → "sql" / "rag" / "hybrid")
- RAG pipeline (`_retrieve()`, `crag_pipeline()`, `run_rag()`)
- SQL generation (`_run_sql_inline()` calls `_sql_service.generate_sql()`)
- Hybrid answer synthesis (`_run_hybrid_inline()`)

**`vectraiq/core/graph.py`** implements the same concerns as graph nodes:
- `route_intent` node → calls `classify_intent()` (delegates)
- `generate_answer` node → for RAG intent, calls `run_rag()` again (full pipeline re-run)
- `generate_sql_node` → calls its own `sql_service.generate_sql()` (different instance)
- `_generate_hybrid_answer()` → independent hybrid synthesis, does NOT use `system_prompt.py`

**Problem:** Any change to SQL generation, hybrid answer synthesis, or intent routing must be evaluated in both files. When `rag_service.py` was updated to use `_sql_service` singleton in Phase 3, `graph.py`'s `sql_service = SQLService()` remained separate and was not updated.

**Specific duplicate functions:**

| Function | rag_service.py | graph.py |
|---|---|---|
| JSON serialization | Implicit via llm_service | `_safe_json_default()` + `_safe_json_dumps()` — local reimplementation |
| Hybrid answer synthesis | `_run_hybrid_inline()` | `_generate_hybrid_answer()` — different prompt, no system prompt |
| SQL execute | Delegates to `_sql_service` | Delegates to `sql_service` (different instance) |

### 1B. Three SQLService Instances

```
rag_service.py:    _sql_service = SQLService()      # module-level (Phase 3 fix)
graph.py:          sql_service = SQLService()         # module-level
query.py:          # does not create one — uses graph
```

The `_schema_context` cache inside `SQLService` is instance-level, so these two instances build their own schema caches independently. Two DB round-trips for schema introspection on first call, two in-memory caches.

### 1C. Two OpenAI Client Instances

```python
# vectraiq/ai/llm_service.py
_client = OpenAI(api_key=settings.openai_api_key)

# vectraiq/ai/embedding_service.py
_openai_client = OpenAI(api_key=settings.openai_api_key)
```

These are module-level singletons (good), but two separate clients. Each maintains its own HTTP connection pool. They should share one `OpenAI` client imported from a shared location.

### 1D. `_safe_json_default` Reimplemented in `graph.py`

`graph.py` contains `_safe_json_default` and `_safe_json_dumps` as private helpers. These are not imported from any shared utility; they are copy-paste implementations of a common pattern.

---

## 2. Dead Code

### 2A. `output_validator.py` — Never Called

**File:** `vectraiq/security/output_validator.py`  
**Function:** `validate_with_retry(raw_str, llm_fn, max_retries)`  
**Status:** Imported in `vectraiq/security/__init__.py`, but `validate_with_retry` is never called from `api/query.py`, `core/graph.py`, or any other production file.

The security pipeline has 9 documented layers. Layer 9 ("output moderation") runs PII redaction via `moderate_and_redact()` from `content_moderation.py`. The output validator (structured schema enforcement with LLM retry) was intended as an additional layer but was never wired in.

**Options:** Wire it in after `moderate_and_redact()` in `api/query.py`, or remove it.

### 2B. `finalize()` Node in LangGraph

**File:** `vectraiq/core/graph.py`  
**Code:**
```python
def finalize(state: GraphState) -> GraphState:
    return {}
```

This node is in the graph topology (`graph.add_node("finalize", finalize)`) and is the terminal node. It takes the state and returns an empty dict — doing nothing. It exists as a placeholder for post-processing logic that was never added. The graph would function identically without it.

### 2C. Unused GraphState Fields

**File:** `vectraiq/core/state.py`

These fields are declared in `GraphState` TypedDict but are never written by any graph node:

| Field | Declared | Written | Read |
|---|---|---|---|
| `cache_hits` | Yes | Never | Never |
| `cost_saved_usd` | Yes | Never | Never |
| `hypotheses` | Yes | Never | Never |
| `reranked_chunks` | Yes | Never | Never |
| `crag_evaluation` | Yes | Never | Never |
| `web_results` | Yes | Never | Never |
| `rag_cache_hit` | Yes | Never | Never |
| `sql_cache_hit` | Yes | Never | Never |
| `chunk_previews` | Yes | `generate_answer` writes it | Never read |

These fields inflate the state object and mislead readers into thinking these values are being tracked when they are not.

### 2D. `python-multipart` Dependency

`python-multipart` is in `pyproject.toml` as a runtime dependency. FastAPI requires it for file upload handling. However, the `/documents/upload` endpoint does not exist. This is a runtime dependency that has no active call site.

### 2E. Stale `_DOCUMENT_HINTS` in `router_service.py`

```python
_DOCUMENT_HINTS = {
    "elastic-cache": "sql",
    "llada": "rag",
    "gsm8k": "rag",
    "humaneval": "rag",
    "qkv": "rag",
}
```

These hints reference ML paper benchmarks (`gsm8k`, `humaneval`), an ML model (`llada`), and attention mechanism terminology (`qkv`) — none of which are relevant to the Kubernetes IT-Operations domain. These are stale from a previous project. The router uses them to override the LLM's classification, so they could cause `k8s_pod` to be misclassified if any query happens to contain one of these terms.

### 2F. `local_storage.py` Is Still Empty

**File:** `vectraiq/storage/local_storage.py`  
**Contents:** 1-line file (just a comment or class stub)

`DocCacheService` with `storage_backend="local"` will fail. This was noted in Phase 0 audit and remains unresolved.

---

## 3. Oversized Functions

### 3A. `run_rag()` in `rag_service.py`

Function handles:
1. Cache key computation
2. Cache hit check
3. Intent classification (LLM call)
4. RAG path execution
5. SQL path execution  
6. Hybrid path execution
7. Cache write
8. Response construction

Each path itself calls 3-5 sub-services. The function is a hub — readable but long. No immediate action required, but it's the main target if the dual-path issue is ever resolved.

### 3B. `generate_answer()` in `graph.py`

Handles three mutually exclusive intents (`sql`, `rag`, `hybrid`) with different code paths inside one function. The `rag` path re-runs `run_rag()` — duplicating the pipeline.

---

## 4. Magic Constants

| Constant | Value | Location | Issue |
|---|---|---|---|
| `VECTOR_SIZE` | `1536` | `vector_store.py` | Not derived from `settings.embedding_model` — will break if model changes |
| `confidence` (RAG) | `0.7` | `rag_service.py` | Hardcoded — not computed |
| `confidence` (SQL) | `0.9` | `rag_service.py` | Hardcoded |
| `confidence` (Hybrid) | `0.8` | `rag_service.py` | Hardcoded |
| `num_threads=8` | `8` | `document_processor.py` | Not configurable via settings |
| `AcceleratorDevice.MPS` | Apple GPU | `document_processor.py` | Platform-locked |
| Scroll limit `10000` | `10000` | `vector_store.py` | Not in config; would silently truncate if collection exceeds 10K docs |

---

## 5. Inconsistent Logging Backends

### Files Using stdlib `logging`

- `vectraiq/ai/crag.py`
- `vectraiq/ai/self_reflective.py`
- `vectraiq/ai/web_search.py`
- `vectraiq/ai/router_service.py`

### Files Using loguru

- `vectraiq/main.py`, `vectraiq/api/*.py`, `vectraiq/middleware/*.py`
- `vectraiq/ai/rag_service.py`, `vectraiq/ai/llm_service.py`, `vectraiq/ai/reranking.py`
- `vectraiq/ai/document_processor.py`

**Impact:** All stdlib loggers route through loguru's `_StdlibHandler` (correct), but they pass through as `logging.LogRecord` objects. The loguru patcher that injects `request_id` only applies to loguru-native records. Stdlib-originated log lines will show `request_id=-` even mid-request.

**Fix:** Replace `import logging; logger = logging.getLogger(__name__)` with `from loguru import logger` in the four affected files.

---

## 6. Type Annotation Gaps

| Location | Issue |
|---|---|
| `graph.py` `retrieve_rag()` | Creates anonymous objects with `type("Chunk", (), {...})()` — bypasses `RetrievedChunk` type entirely |
| `graph.py` `generate_answer()` | Return type annotated as `dict[str, Any]` — GraphState mutations are untyped |
| `rag_service.py` `_retrieve()` | `flags: dict | None = None` — `flags` dict keys are undocumented |
| `api/admin.py` `cache_clear()` | Returns `dict[str, Any]` — not typed with a Pydantic response model |
| `vector_store.py` `get_client()` | Creates a new `QdrantClient` each call with no return type cache |

---

## 7. Naming Inconsistencies

| Inconsistency | Detail |
|---|---|
| `SqlApprovalRequest` in models vs `SqlExecuteRequest` in old code | Name changed but referenced as "execute" in docstrings |
| `_sql_service` (rag_service) vs `sql_service` (graph) | Both are module-level SQLService instances, different visibility conventions |
| `_client` (llm_service) vs `_openai_client` (embedding_service) | Two OpenAI client singletons with different internal names |
| `generate` / `generate_with_json` (llm_service) | Reasonable names, but `generate_with_json` implies structured output — not immediately obvious it's a JSON-mode call |
| `run_rag()` | Name implies retrieval but performs full retrieve + generate pipeline |
| `retrieve_rag` node in graph | Node is named "retrieve" but runs full RAG pipeline including generation when intent=rag (via generate_answer node, which calls run_rag again) |

---

## 8. Code Smells

### 8A. Anonymous Object in `graph.py`

```python
# graph.py retrieve_rag node
spotlighted_context = build_spotlighted_context([
    type("Chunk", (), {"text": src, "source": src, "score": 1.0})()
    for src in response.sources
])
```

This creates throwaway anonymous objects to satisfy the `build_spotlighted_context` interface. It passes source document names as `text` and `source` (they're the same string), and assigns a fake `score=1.0`. The actual chunk texts and scores from the retrieval are discarded.

This means in the hybrid path, the spotlighting step has no actual content — only document names. The spotlighted context would be nearly empty.

### 8B. `self_reflective.py` Empty User Message

```python
result = generate_with_json(
    system_prompt=formatted_prompt,  # The entire multi-paragraph reflection prompt
    user_message="",                  # Empty
    model=settings.llm_model_grader,
)
```

The OASST/ChatML convention expects a non-empty human turn. Passing an empty string as the user message and the full prompt as system prompt is unconventional. This works today with GPT-4o-mini, but is fragile with other providers.

### 8C. `fuse_rrf` Key Collision Risk

```python
# sparse_vector_service.py
doc_scores: dict[str, float] = {}
for rank, chunk in enumerate(results):
    doc_scores[chunk.text] = ...  # chunk.text as dict key
```

RRF fusion uses the raw chunk text as the deduplication key. For a Kubernetes docs corpus with repeated warning messages, boilerplate headers, or identical snippets from multiple files, this will silently merge chunks from different sources, potentially losing source diversity.

---

## Summary

| Category | Count | Severity |
|---|---|---|
| Duplicate logic (dual execution path) | 1 systemic issue | CRITICAL |
| Dead code items | 6 items | HIGH |
| Magic constants | 7 constants | MEDIUM |
| Logging inconsistencies | 4 files | MEDIUM |
| Type annotation gaps | 5 locations | MEDIUM |
| Code smells | 3 items | LOW-MEDIUM |
| Oversized functions | 2 functions | LOW |
| Naming inconsistencies | 7 items | LOW |

The codebase is in good shape for a project at this stage. The dual-execution-path issue is the only structural problem — all other findings are minor and won't block Phase 4. The dead code and magic constants should be cleaned up before public deployment.
