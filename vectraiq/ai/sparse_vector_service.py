import threading

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from vectraiq.models import RetrievedChunk


class SparseVectorIndex:
    """TF-IDF sparse vector index with thread-safe fit/search."""

    def __init__(self) -> None:
        self.vectorizer = TfidfVectorizer(stop_words="english")
        self.documents: list[dict] = []
        self.matrix = None
        self._lock = threading.RLock()

    def fit(self, documents: list[dict]) -> None:
        with self._lock:
            self.documents = documents
            if not documents:
                self.matrix = None
                return
            texts = [doc.get("text", "") for doc in documents]
            try:
                self.matrix = self.vectorizer.fit_transform(texts)
            except ValueError:
                self.matrix = None
                return
            if self.matrix.shape[1] == 0:
                self.matrix = None

    def search(self, query: str, top_k: int = 20) -> list[RetrievedChunk]:
        with self._lock:
            if self.matrix is None or not self.documents:
                return []
            query_vec = self.vectorizer.transform([query])
            similarities = cosine_similarity(query_vec, self.matrix).flatten()
            top_indices = similarities.argsort()[::-1][:top_k]
            results: list[RetrievedChunk] = []
            for idx in top_indices:
                score = float(similarities[idx])
                if score <= 0:
                    continue
                doc = self.documents[idx]
                results.append(
                    RetrievedChunk(
                        text=doc.get("text", ""),
                        source=doc.get("source", ""),
                        score=score,
                    )
                )
            return results


def fuse_rrf(
    result_lists: list[list[RetrievedChunk]],
    rrf_k: int = 60,
) -> list[RetrievedChunk]:
    """Reciprocal Rank Fusion over multiple ranked result lists."""
    scores: dict[str, float] = {}
    meta: dict[str, dict] = {}

    for result_list in result_lists:
        for rank, chunk in enumerate(result_list):
            key = chunk.text
            scores[key] = scores.get(key, 0.0) + 1.0 / (rrf_k + rank + 1)
            if key not in meta:
                meta[key] = {"text": chunk.text, "source": chunk.source}

    return [
        RetrievedChunk(text=text, source=meta[text]["source"], score=score)
        for text, score in sorted(scores.items(), key=lambda x: x[1], reverse=True)
    ]
