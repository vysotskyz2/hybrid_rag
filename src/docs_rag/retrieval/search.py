from __future__ import annotations

from qdrant_client import models

from docs_rag.retrieval.embeddings import DenseEmbedder, SparseEmbedder
from docs_rag.retrieval.models import SearchFilters, SearchMode, SearchResult
from docs_rag.retrieval.store import QdrantStore


class Retriever:
    def __init__(
        self,
        store: QdrantStore,
        dense: DenseEmbedder,
        sparse: SparseEmbedder,
        candidates: int = 30,
    ) -> None:
        if candidates <= 0:
            raise ValueError("candidates must be positive")
        self._store = store
        self._dense = dense
        self._sparse = sparse
        self._candidates = candidates

    def search(
        self,
        query: str,
        mode: SearchMode = "hybrid",
        top_k: int = 5,
        filters: SearchFilters | None = None,
    ) -> list[SearchResult]:
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        if not query.strip():
            raise ValueError("query must not be empty")

        if mode == "dense":
            points = self._store.search_dense(
                self._dense.embed_query(query),
                limit=top_k,
                filters=filters,
            )
        elif mode == "sparse":
            points = self._store.search_sparse(
                self._sparse.embed_query(query),
                limit=top_k,
                filters=filters,
            )
        elif mode == "hybrid":
            points = self._store.search_hybrid(
                self._dense.embed_query(query),
                self._sparse.embed_query(query),
                limit=top_k,
                candidates=self._candidates,
                filters=filters,
            )
        else:
            raise ValueError(f"Unsupported search mode: {mode}")

        return [_to_result(point) for point in points]


def _to_result(point: models.ScoredPoint) -> SearchResult:
    payload = point.payload or {}
    return SearchResult(
        chunk_id=str(point.id),
        score=float(point.score),
        path=str(payload.get("path", "")),
        url=str(payload.get("url", "")),
        title=str(payload.get("title", "")),
        heading_path=str(payload.get("heading_path", "")),
        section=str(payload.get("section", "")),
        content_type=str(payload.get("content_type", "")),
        language=str(payload.get("language", "")),
        version=str(payload.get("version", "")),
        token_count=int(payload.get("token_count", 0)),
        text=str(payload.get("text", "")),
    )
