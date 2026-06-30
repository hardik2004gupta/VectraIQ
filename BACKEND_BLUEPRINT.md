# VectraIQ v2 — Backend Architecture Blueprint
**Version:** 2.0  
**Status:** Design Phase  

---

## Architectural Pattern

VectraIQ v2 uses **Clean Architecture** (also known as Ports and Adapters / Hexagonal Architecture). Dependencies always point inward:

```
   ┌─────────────────────────────────┐
   │           API Layer             │  ← HTTP, routing, middleware
   │  ┌──────────────────────────┐   │
   │  │     Application Layer    │   │  ← Use cases, orchestration
   │  │  ┌───────────────────┐   │   │
   │  │  │   Domain Layer    │   │   │  ← Entities, interfaces, value objects
   │  │  └───────────────────┘   │   │
   │  │  Infrastructure Layer    │   │  ← DB, cache, storage, external APIs
   │  └──────────────────────────┘   │
   │  AI Engine (cross-cutting)      │  ← Pure AI logic, injected as services
   └─────────────────────────────────┘
   Core Utilities (used everywhere)
```

**Rule:** Inner layers never import from outer layers. The domain layer has zero external dependencies.

---

## Layer 1 — Domain Layer

**Location:** `apps/api/src/domain/`  
**Dependencies:** None (stdlib only)  
**Testing:** No mocking required

### Entities

Entities are rich Python dataclasses with business logic. They are the language of the application.

#### `User`
```
Fields: id, username, password_hash, role (user|admin|superadmin), 
        is_active, created_at, last_login_at
Methods: is_admin() → bool, is_active() → bool
```

#### `Document`
```
Fields: id, name, original_filename, content_hash, status 
        (pending|processing|indexed|failed), chunk_count,
        uploaded_by, created_at, metadata (dict)
Methods: is_indexed() → bool, is_processing() → bool
```

#### `RetrievedChunk`
```
Fields: text (str), source (str), score (float), chunk_id (str | None),
        page_number (int | None)
No methods — pure data container
```

#### `QueryResult`
```
Fields: answer (str), sources (list[str]), confidence (float),
        route (RAG|SQL|HYBRID), chunks (list[RetrievedChunk]),
        cache_hit (bool), reflection_iterations (int),
        reflection_score (float | None), refined_question (str | None),
        pending_sql (PendingSQL | None), metadata (dict)
```

#### `PendingSQL`
```
Fields: sql (str), query_id (str), explanation (str)
```

#### `Conversation`
```
Fields: id, user_id, turns (list[Turn]), created_at
Turn: question (str), answer (str), route, timestamp
```

### Repository Interfaces (Ports)

Abstract interfaces that the application layer depends on. Infrastructure layer provides the implementations.

#### `UserRepository` (abstract)
```
get_by_username(username: str) → User | None
create(username: str, password_hash: str) → User
update_last_login(user_id: str) → None
```

#### `DocumentRepository` (abstract)
```
create(document: Document) → Document
get_by_id(doc_id: str) → Document | None
get_by_hash(content_hash: str) → Document | None
list_by_user(user_id: str, limit: int, cursor: str | None) → (list[Document], str | None)
update_status(doc_id: str, status: str, chunk_count: int) → None
delete(doc_id: str) → None
```

#### `VectorRepository` (abstract)
```
upsert_chunks(chunks: list[RetrievedChunk], embeddings: list[list[float]]) → None
search_dense(embedding: list[float], top_k: int) → list[RetrievedChunk]
search_hybrid(embedding: list[float], query_text: str, top_k: int) → list[RetrievedChunk]
scroll_all(limit: int) → list[dict]
ensure_collection() → None
```

#### `CacheRepository` (abstract)
```
get(key: str) → str | None
set(key: str, value: str, ttl_seconds: int) → None
delete(key: str) → None
clear_namespace(namespace: str) → int   # returns count cleared
pipeline_execute(ops: list[CacheOp]) → list[Any]
```

#### `StorageRepository` (abstract)
```
upload(key: str, data: bytes, content_type: str) → str   # returns URL
download(key: str) → bytes
exists(key: str) → bool
delete(key: str) → None
```

### Value Objects

Immutable objects with no identity.

#### `Intent`
```python
class Intent(str, Enum):
    RAG = "rag"
    SQL = "sql"
    HYBRID = "hybrid"
```

#### `SearchMode`
```python
class SearchMode(str, Enum):
    DENSE = "dense"
    SPARSE = "sparse"
    HYBRID = "hybrid"
```

#### `QueryFlags`
```python
@dataclass(frozen=True)
class QueryFlags:
    search_mode: SearchMode = SearchMode.HYBRID
    top_k: int = 5
    enable_hyde: bool = False
    enable_rerank: bool = True
    enable_crag: bool = True
    enable_self_reflective: bool = False
```

---

## Layer 2 — Infrastructure Layer

**Location:** `apps/api/src/infrastructure/`  
**Dependencies:** psycopg, qdrant-client, upstash-redis, boto3, openai, tavily, voyageai  
**Testing:** Integration tests with real or containerized services

### Database (`infrastructure/db/`)

#### Connection Pool
```
Singleton psycopg v3 AsyncConnectionPool
Pool size: min=2, max=10 (configurable)
Startup check: validate connectivity before accepting requests
Connection string from: settings.database_url
```

#### Migration Runner
```
Sequential SQL files in infrastructure/db/migrations/
Tracked by a _migrations table in Postgres
Idempotent: each migration checks if already applied
Run at: application startup (before routes open)
```

#### `PgUserRepository` implements `UserRepository`
- Uses parameterized psycopg v3 queries
- Password hash comparison done in Python (bcrypt), not Postgres
- No ORM — raw SQL for predictability

#### `PgDocumentRepository` implements `DocumentRepository`
- Cursor-based pagination (no OFFSET — performant at scale)
- Soft deletes: `deleted_at` column, filtered in all reads

### Vector Database (`infrastructure/vector/`)

#### `QdrantRepository` implements `VectorRepository`
- Single shared `QdrantClient` instance (singleton)
- Collection name from `settings.qdrant_collection`
- Dense search: `query_points` with cosine distance
- Sparse index delegated to `ai/retriever/sparse_retriever.py`
- `scroll_all()` used only during sparse index rebuild, not per-query

### Cache (`infrastructure/cache/`)

#### `RedisRepository` implements `CacheRepository`
- `upstash-redis` HTTP client (works in serverless environments)
- SHA-256 key hashing: `{namespace}:{sha256(raw_key)}`
- All cache keys prefixed with `vectraiq:v2:`
- `clear_namespace()` uses SCAN + DEL in batches of 100

#### `MemoryRepository` implements `CacheRepository`
- Thread-safe `OrderedDict` with LRU eviction
- Max 500 entries (configurable)
- TTL enforced by checking expiry timestamp on read
- Used when Redis is not configured or unavailable

#### `TieredCacheRepository`
- Wraps both Redis and Memory
- Read: try Redis first, fall back to Memory
- Write: write to both Redis and Memory
- Exposed as the single `CacheRepository` to the application layer

### Storage (`infrastructure/storage/`)

#### `R2StorageRepository` implements `StorageRepository`
- Cloudflare R2 via S3-compatible boto3 client
- Bucket configured from `settings.r2_bucket_name`
- Returns public CDN URLs for uploaded files
- Used for raw document storage (before processing)

#### `LocalStorageRepository` implements `StorageRepository`
- Stores bytes in `{settings.local_storage_path}/{key}`
- For development only — `storage_backend=local` env var
- Returns `file://` URLs

### External Providers (`infrastructure/providers/`)

These wrap external API calls. They are injected into AI modules.

#### `OpenAIProvider`
```
generate(system: str, user: str, model: str, json_mode: bool) → GenerateResult
embed(texts: list[str], model: str) → list[list[float]]
```
- Async by default
- Retries: 3 attempts with exponential backoff (via tenacity)
- Timeout: 30s per call

#### `TavilyProvider`
```
search(query: str, max_results: int) → list[WebResult]
```

#### `VoyageProvider`
```
rerank(query: str, documents: list[str], top_k: int) → list[RerankResult]
```

---

## Layer 3 — Application Layer

**Location:** `apps/api/src/application/`  
**Dependencies:** Domain interfaces only (no concrete implementations)  
**Testing:** Unit tests with mock repositories

### Use Cases

Each use case is a Python class with an `execute()` method. Use cases are injected with repository interfaces at construction time.

#### `QueryUseCase`

```
Constructor: 
  vector_repo: VectorRepository
  cache_repo: CacheRepository  
  llm_provider: LLMProvider
  + all AI module instances

execute(question: str, user_id: str, flags: QueryFlags) → QueryResult

Responsibilities:
  1. Check RAG answer cache
  2. Invoke AI orchestrator (LangGraph)
  3. Apply output security scan
  4. Store result in cache
  5. Log query analytics
  6. Consume token budget
  7. Return QueryResult
```

#### `DocumentUseCase`

```
Constructor:
  document_repo: DocumentRepository
  vector_repo: VectorRepository
  storage_repo: StorageRepository
  cache_repo: CacheRepository
  document_processor: DocumentProcessor
  embedding_service: EmbeddingService

execute_upload(file: bytes, filename: str, user_id: str) → Document

Responsibilities:
  1. Compute content hash
  2. Check if already indexed (dedup)
  3. Store raw file in R2/local
  4. Parse document (Docling)
  5. Embed chunks (batched)
  6. Upsert to Qdrant
  7. Save metadata to Postgres
  8. Invalidate sparse index (trigger rebuild)
  9. Return Document entity
```

#### `AuthUseCase`

```
Constructor:
  user_repo: UserRepository
  
register(username: str, password: str) → (User, token: str)
login(username: str, password: str) → (User, token: str)
```

#### `AnalyticsUseCase`

```
Constructor:
  cache_repo: CacheRepository
  document_repo: DocumentRepository

get_usage_stats(user_id: str, days: int) → UsageStats
get_cache_stats() → CacheStats
```

### AI Orchestrator (`application/orchestrator.py`)

The LangGraph graph is built once at application startup and stored as a singleton. The orchestrator wraps the graph and provides a clean interface.

```
class AIOrchestrator:
    _graph: CompiledGraph  # singleton
    
    async def run(
        question: str,
        user_id: str,
        flags: QueryFlags,
    ) → QueryResult
    
    async def stream(
        question: str,
        user_id: str,
        flags: QueryFlags,
    ) → AsyncGenerator[StreamEvent, None]
    
    async def resume_sql_approval(
        query_id: str,
        approved: bool,
    ) → QueryResult
```

---

## Layer 4 — API Layer

**Location:** `apps/api/src/api/`  
**Dependencies:** Application layer use cases (injected via FastAPI Depends)  
**Testing:** API tests with TestClient

### Dependency Injection

FastAPI's `Depends()` is the DI container. All dependencies are constructed once at startup via lifespan events and injected into route handlers.

```python
# Startup: build all singletons
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Validate all required env vars
    startup.validate_settings()
    
    # Initialize infrastructure
    db_pool = await create_db_pool(settings.database_url)
    redis = RedisRepository(settings.upstash_redis_url, settings.upstash_redis_token)
    qdrant = QdrantRepository(settings.qdrant_url, settings.qdrant_collection)
    storage = build_storage_backend(settings.storage_backend)
    
    # Initialize AI singletons
    sparse_index = SparseIndex()  # builds from Qdrant on startup
    reranker = build_reranker(settings.reranker_backend)
    
    # Build use cases
    query_uc = QueryUseCase(qdrant, redis, openai_provider, sparse_index, reranker, ...)
    doc_uc = DocumentUseCase(doc_repo, qdrant, storage, redis, processor, embedding_svc)
    
    # Store in app.state for dependency injection
    app.state.query_uc = query_uc
    app.state.doc_uc = doc_uc
    
    yield
    
    # Cleanup
    await db_pool.close()
```

### API Schemas (v1)

All schemas are Pydantic v2 models. Request schemas validate and sanitize. Response schemas serialize cleanly.

#### `QueryRequest`
```
question: str (min=1, max=2000, injection-validated)
flags: QueryFlags (optional, defaults applied server-side)
stream: bool = False
```

#### `ChatResponse`
```
answer: str
sources: list[str]
confidence: float (0.0–1.0)
route: Literal["rag", "sql", "hybrid"]
cache_hit: bool
cost_saved: str (computed from cache hits × token cost)
metadata: ResponseMetadata
pending_sql: PendingSQL | None
```

#### `StreamEvent` (SSE)
```
event: Literal["token", "sources", "metadata", "done", "error"]
data: str (JSON)
```

### Middleware Stack (in order of execution)

1. **`TracingMiddleware`** — injects `trace_id` into request state and log context
2. **`LoggingMiddleware`** — logs request start/end with timing and status code
3. **`CORSMiddleware`** — configured to allow Next.js origin (from settings)
4. **`AuthMiddleware`** — validates JWT, populates `request.state.user`
5. **`RateLimitMiddleware`** — Redis sliding window per user
6. **`TokenBudgetMiddleware`** — daily cap per user

Security scanning (llm-guard) and PII redaction happen **inside the use case**, not in middleware, because they need access to the processed text after restructuring.

### Error Handling

Typed exception hierarchy in `core/exceptions.py`:

```
VectraIQException (base)
├── AuthError (401)
│   ├── InvalidCredentialsError
│   └── TokenExpiredError
├── ForbiddenError (403)
├── ValidationError (400)
│   ├── InjectionDetectedError
│   ├── ContentBlockedError
│   └── TokenLimitExceededError  
├── RateLimitError (429)
├── TokenBudgetError (429)
├── DocumentError (422)
│   ├── DuplicateDocumentError
│   └── ProcessingFailedError
├── AIError (500)
│   ├── LLMCallFailedError
│   └── RetrievalFailedError
└── InfrastructureError (503)
    ├── DatabaseError
    ├── VectorStoreError
    └── CacheError
```

FastAPI exception handlers map each exception type to the correct HTTP status code and error response format.

---

## Layer 5 — Core Utilities

**Location:** `apps/api/src/core/`  
**Dependencies:** stdlib + pydantic-settings only

### `config.py` — Settings

Pydantic `BaseSettings` with startup validation. Every field has a type and is validated at import time. Startup check ensures no placeholder values reach production.

```python
class Settings(BaseSettings):
    # App
    app_name: str = "VectraIQ"
    app_version: str = "2.0.0"
    debug: bool = False
    
    # Auth
    jwt_secret: str  # REQUIRED — no default
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 60
    
    # OpenAI
    openai_api_key: str  # REQUIRED
    llm_model_answer: str = "gpt-4o"
    llm_model_grader: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    
    # Databases
    database_url: str  # REQUIRED
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "vectraiq_documents"
    
    # Cache
    upstash_redis_url: str = ""
    upstash_redis_token: str = ""
    
    # Storage
    storage_backend: Literal["local", "r2", "s3"] = "local"
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = ""
    
    # Security
    allowed_origins: list[str] = ["http://localhost:3000"]
    rate_limit_requests: int = 20
    rate_limit_window_seconds: int = 60
    max_tokens_per_user_daily: int = 100_000
    
    # AI Features
    hyde_num_hypotheses: int = 3
    reranker_backend: Literal["local", "voyage"] = "local"
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    reranker_initial_top_k: int = 20
    crag_relevance_threshold: float = 0.7
    reflection_min_score: float = 0.85
    max_reflection_retries: int = 2
    
    # External
    tavily_api_key: str = ""
    voyage_api_key: str = ""
    
    # Logging
    log_level: str = "INFO"
    log_json: bool = False
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    
    @model_validator(mode="after")
    def validate_required_secrets(self) -> "Settings":
        if not self.jwt_secret or self.jwt_secret == "change-me":
            raise ValueError("JWT_SECRET must be set to a secure random value")
        if len(self.jwt_secret) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters")
        return self
```

### `startup.py` — Pre-flight Checks

```python
async def run_startup_checks(settings: Settings) → None:
    """Validate connectivity to all required services before accepting requests."""
    checks = [
        check_postgres(settings.database_url),
        check_qdrant(settings.qdrant_url),
    ]
    if settings.upstash_redis_url:
        checks.append(check_redis(settings.upstash_redis_url, settings.upstash_redis_token))
    
    results = await asyncio.gather(*checks, return_exceptions=True)
    failed = [name for name, result in results if isinstance(result, Exception)]
    
    if failed:
        raise RuntimeError(f"Startup failed: {failed}")
    
    logger.info("All startup checks passed")
```

### `exceptions.py` — Error Types

Typed exceptions with HTTP status codes embedded:

```python
class VectraIQException(Exception):
    status_code: int = 500
    error_code: str = "internal_error"
    
class InjectionDetectedError(VectraIQException):
    status_code = 400
    error_code = "injection_detected"
```

---

## Dependency Injection Map

```
FastAPI lifespan
└── creates singletons:
    ├── db_pool (AsyncConnectionPool)
    ├── redis (TieredCacheRepository)
    ├── qdrant (QdrantRepository)
    ├── storage (R2StorageRepository | LocalStorageRepository)
    ├── openai_provider (OpenAIProvider)
    ├── sparse_index (SparseIndex)  ← built from Qdrant at startup
    ├── reranker (CrossEncoder | VoyageReranker)  ← model loaded at startup
    ├── embedding_svc (EmbeddingService)
    └── sql_schema_inspector (SchemaInspector)  ← queried at startup

Use cases (constructed in lifespan, stored in app.state):
    ├── query_uc (QueryUseCase)
    ├── doc_uc (DocumentUseCase)
    ├── auth_uc (AuthUseCase)
    └── analytics_uc (AnalyticsUseCase)

Route handlers:
    └── get use case from app.state via Depends(get_query_uc)
```

---

## Key Improvements Over v1

| Issue in v1 | Solution in v2 |
|---|---|
| Dual execution paths (graph + rag_service) | Single path: use case → orchestrator → AI modules |
| Reranker instantiated per request | Singleton at startup, injected via DI |
| Sparse index rebuilt every query | Singleton at startup, background refresh after document uploads |
| SQLService schema cache lost per-instance | Singleton `SchemaInspector`, queried once at startup |
| psycopg v2/v3 mixing | psycopg v3 only, everywhere |
| `local_storage.py` empty | Fully implemented `LocalStorageRepository` |
| No upload endpoint | `DocumentUseCase` + `/api/v1/documents/upload` route |
| No startup validation | `startup.py` pre-flight checks + Settings validator |
| No connection pooling | `AsyncConnectionPool` at startup |
| No tests | Full test pyramid (unit, integration, API) |
| Redis clear is no-op | `clear_namespace()` uses SCAN + DEL |
| SQL approval not user-scoped | `user_id` in LangGraph state, validated in resume |
