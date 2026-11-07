from __future__ import annotations

from docs_rag.retrieval.models import SearchFilters, SearchMode, SearchResult
from docs_rag.retrieval.reranker import CrossEncoderReranker
from docs_rag.retrieval.search import Retriever


class SearchService:
    def __init__(
        self,
        retriever: Retriever,
        reranker: CrossEncoderReranker | None = None,
        candidates: int = 20,
    ) -> None:
        if candidates <= 0:
            raise ValueError("candidates must be positive")
        self._retriever = retriever
        self._reranker = reranker
        self._candidates = candidates

    @property
    def rerank_enabled(self) -> bool:
        return self._reranker is not None

    def search(
        self,
        query: str,
        mode: SearchMode = "hybrid",
        top_k: int = 5,
        filters: SearchFilters | None = None,
        rerank: bool = True,
    ) -> list[SearchResult]:
        if top_k <= 0:
            raise ValueError("top_k must be positive")

        reranker = self._reranker if rerank else None
        candidate_k = max(top_k, self._candidates) if reranker is not None else top_k
        results = self._retriever.search(
            query=query,
            mode=mode,
            top_k=candidate_k,
            filters=filters,
        )

        if reranker is not None and results:
            return reranker.rerank(query, results, top_k)

        return results[:top_k]
