from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from vectraiq.config import settings
from vectraiq.models import RetrievedChunk

if TYPE_CHECKING:
    from vectraiq.ai.sparse_vector_service import SparseVectorIndex

VECTOR_SIZE = 1536

# ── Qdrant client singleton ───────────────────────────────────────────────────

_qdrant_client: QdrantClient | None = None


def get_client() -> QdrantClient:
    """Return the module-level QdrantClient singleton (created once per process)."""
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient(url=settings.qdrant_url, timeout=30)
    return _qdrant_client


# ── Sparse index singleton ────────────────────────────────────────────────────
# Rebuilt at most every _SPARSE_INDEX_TTL_SECONDS to avoid rescrolling 10k docs
# on every hybrid/sparse query.

_sparse_index: SparseVectorIndex | None = None
_sparse_index_built_at: float = 0.0
_SPARSE_INDEX_TTL_SECONDS: float = 1800.0  # 30-minute TTL


def _get_sparse_index() -> SparseVectorIndex:
    """Return a cached TF-IDF index, rebuilding only when TTL has expired."""
    global _sparse_index, _sparse_index_built_at
    now = time.time()
    if _sparse_index is None or (now - _sparse_index_built_at) > _SPARSE_INDEX_TTL_SECONDS:
        _sparse_index = _build_sparse_index()
        _sparse_index_built_at = now
    return _sparse_index


def invalidate_sparse_index() -> None:
    """Force rebuild of the sparse index on the next sparse/hybrid query.

    Call this after upserting new documents so the TF-IDF vocabulary stays
    current without waiting for the TTL to expire.
    """
    global _sparse_index, _sparse_index_built_at
    _sparse_index = None
    _sparse_index_built_at = 0.0


# ── Core operations ───────────────────────────────────────────────────────────

def ensure_collection() -> None:
    client = get_client()
    existing = {c.name for c in client.get_collections().collections}
    if settings.qdrant_collection not in existing:
        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )


def upsert_chunks(chunks: list[RetrievedChunk], embeddings: list[list[float]]) -> None:
    ensure_collection()
    client = get_client()
    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=embedding,
            payload={"text": chunk.text, "source": chunk.source},
        )
        for chunk, embedding in zip(chunks, embeddings, strict=True)
    ]
    client.upsert(collection_name=settings.qdrant_collection, points=points)
    # Invalidate so the next sparse/hybrid query sees the new documents
    invalidate_sparse_index()


def search(query_embedding: list[float], top_k: int = 5) -> list[RetrievedChunk]:
    client = get_client()
    results = client.query_points(
        collection_name=settings.qdrant_collection,
        query=query_embedding,
        limit=top_k,
        with_payload=True,
    ).points
    return [
        RetrievedChunk(
            text=p.payload.get("text", ""),
            source=p.payload.get("source", ""),
            score=float(p.score),
        )
        for p in results
    ]


def _build_sparse_index() -> SparseVectorIndex:
    from vectraiq.ai.sparse_vector_service import SparseVectorIndex

    client = get_client()
    all_points, _ = client.scroll(
        collection_name=settings.qdrant_collection,
        limit=10000,
        with_payload=True,
        with_vectors=False,
    )
    documents = [
        {
            "text": point.payload.get("text", "") if point.payload else "",
            "source": point.payload.get("source", "") if point.payload else "",
            "id": str(point.id),
        }
        for point in all_points
    ]
    index = SparseVectorIndex()
    index.fit(documents)
    return index


def sparse_search(query_text: str, top_k: int = 5) -> list[RetrievedChunk]:
    return _get_sparse_index().search(query_text, top_k=top_k)


def hybrid_search(
    query_embedding: list[float],
    query_text: str,
    top_k: int = 5,
    rrf_k: int = 60,
    sparse_top_k: int = 20,
) -> list[RetrievedChunk]:
    from vectraiq.ai.sparse_vector_service import fuse_rrf

    # Both operations share the same cached index — no double scroll
    dense_results = search(query_embedding, top_k=sparse_top_k)
    sparse_results = _get_sparse_index().search(query_text, top_k=sparse_top_k)
    fused = fuse_rrf([dense_results, sparse_results], rrf_k=rrf_k)
    return fused[:top_k]
