from dataclasses import replace

import pytest

from docs_rag.retrieval.models import SearchFilters, SearchMode, SearchResult
from docs_rag.retrieval.service import SearchService
from tests.api.helpers import make_search_result


class FakeRetriever:
    def __init__(self, results: list[SearchResult]) -> None:
        self.results = results
        self.calls: list[tuple[str, SearchMode, int, SearchFilters | None]] = []

    def search(
        self,
        query: str,
        mode: SearchMode = "hybrid",
        top_k: int = 5,
        filters: SearchFilters | None = None,
    ) -> list[SearchResult]:
        self.calls.append((query, mode, top_k, filters))
        return self.results[:top_k]


class FakeReranker:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int, int]] = []

    def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int,
    ) -> list[SearchResult]:
        self.calls.append((query, len(results), top_k))
        ranked = [
            replace(result, score=1.0 - index / 10, retrieval_score=result.score)
            for index, result in enumerate(reversed(results))
        ]
        return ranked[:top_k]


def make_results(count: int = 5) -> list[SearchResult]:
    return [
        make_search_result(
            chunk_id=f"chunk-{index}",
            score=float(index),
            retrieval_score=None,
        )
        for index in range(count)
    ]


def test_search_without_reranker_keeps_top_k() -> None:
    retriever = FakeRetriever(make_results())
    service = SearchService(retriever=retriever, candidates=4)  # type: ignore[arg-type]

    results = service.search("query", top_k=2)

    assert len(results) == 2
    assert retriever.calls == [("query", "hybrid", 2, None)]
    assert service.rerank_enabled is False


def test_search_reranks_expanded_candidates() -> None:
    retriever = FakeRetriever(make_results())
    reranker = FakeReranker()
    service = SearchService(
        retriever=retriever,  # type: ignore[arg-type]
        reranker=reranker,  # type: ignore[arg-type]
        candidates=4,
    )

    results = service.search("query", top_k=2)

    assert retriever.calls == [("query", "hybrid", 4, None)]
    assert reranker.calls == [("query", 4, 2)]
    assert [result.chunk_id for result in results] == ["chunk-3", "chunk-2"]
    assert [result.score for result in results] == [1.0, 0.9]
    assert [result.retrieval_score for result in results] == [3.0, 2.0]
    assert service.rerank_enabled is True


def test_search_can_disable_reranking_per_call() -> None:
    retriever = FakeRetriever(make_results())
    reranker = FakeReranker()
    service = SearchService(
        retriever=retriever,  # type: ignore[arg-type]
        reranker=reranker,  # type: ignore[arg-type]
        candidates=4,
    )

    results = service.search("query", top_k=2, rerank=False)

    assert len(results) == 2
    assert retriever.calls == [("query", "hybrid", 2, None)]
    assert reranker.calls == []


def test_search_rejects_invalid_candidates() -> None:
    with pytest.raises(ValueError, match="candidates"):
        SearchService(retriever=FakeRetriever([]), candidates=0)  # type: ignore[arg-type]
