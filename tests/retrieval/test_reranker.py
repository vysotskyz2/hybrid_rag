from typing import Any, cast

import pytest

from docs_rag.retrieval.reranker import CrossEncoderReranker
from tests.api.helpers import make_search_result


class FakeRanker:
    def __init__(self, ranked: list[dict[str, Any]]) -> None:
        self.ranked = ranked
        self.calls: list[tuple[str, list[str], int, int, bool | None]] = []

    def rank(
        self,
        query: str,
        documents: list[str],
        top_k: int | None = None,
        batch_size: int = 32,
        show_progress_bar: bool | None = None,
    ) -> list[dict[str, Any]]:
        self.calls.append((query, documents, top_k or 0, batch_size, show_progress_bar))
        return self.ranked[:top_k]


def make_ranker() -> FakeRanker:
    return FakeRanker(
        [
            {"corpus_id": 2, "score": 0.9},
            {"corpus_id": 0, "score": 0.8},
        ]
    )


def test_rerank_maps_scores_to_results() -> None:
    ranker = make_ranker()
    reranker = CrossEncoderReranker(
        model_name="fake",
        model=cast(Any, ranker),
        batch_size=4,
    )
    results = [
        make_search_result(chunk_id="chunk-0", score=0.1, retrieval_score=None, text="doc0"),
        make_search_result(chunk_id="chunk-1", score=0.2, retrieval_score=None, text="doc1"),
        make_search_result(chunk_id="chunk-2", score=0.3, retrieval_score=None, text="doc2"),
    ]

    reranked = reranker.rerank("query", results, top_k=2)

    assert [result.chunk_id for result in reranked] == ["chunk-2", "chunk-0"]
    assert [result.score for result in reranked] == [0.9, 0.8]
    assert [result.retrieval_score for result in reranked] == [0.3, 0.1]
    assert ranker.calls == [
        ("query", ["doc0", "doc1", "doc2"], 2, 4, False),
    ]


def test_rerank_returns_empty_for_empty_results() -> None:
    ranker = make_ranker()
    reranker = CrossEncoderReranker(model_name="fake", model=cast(Any, ranker))

    assert reranker.rerank("query", [], top_k=3) == []
    assert ranker.calls == []


def test_rerank_rejects_non_positive_top_k() -> None:
    reranker = CrossEncoderReranker(model_name="fake", model=cast(Any, make_ranker()))

    with pytest.raises(ValueError, match="top_k"):
        reranker.rerank("query", [make_search_result()], top_k=0)


def test_reranker_rejects_invalid_batch_size() -> None:
    with pytest.raises(ValueError, match="batch_size"):
        CrossEncoderReranker(model_name="fake", model=cast(Any, make_ranker()), batch_size=0)
