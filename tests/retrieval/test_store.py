import pytest

from docs_rag.retrieval.indexer import build_index
from docs_rag.retrieval.models import SearchFilters
from docs_rag.retrieval.search import Retriever
from docs_rag.retrieval.store import QdrantStore
from tests.retrieval.helpers import make_chunk


def build_test_index(
    store: QdrantStore,
    dense_embedder: object,
    sparse_embedder: object,
    recreate: bool = True,
) -> None:
    chunks = [
        make_chunk("alpha", "alpha dependency injection", "tutorial/alpha.md"),
        make_chunk("beta", "beta background tasks", "advanced/beta.md", section="advanced"),
        make_chunk("gamma", "gamma websockets", "advanced/gamma.md", section="advanced"),
    ]
    build_index(
        chunks=chunks,
        store=store,
        dense=dense_embedder,  # type: ignore[arg-type]
        sparse=sparse_embedder,  # type: ignore[arg-type]
        version="v1",
        batch_size=2,
        recreate=recreate,
    )


def test_index_and_search_modes(
    store: QdrantStore,
    dense_embedder: object,
    sparse_embedder: object,
) -> None:
    build_test_index(store, dense_embedder, sparse_embedder)
    retriever = Retriever(store, dense_embedder, sparse_embedder, candidates=10)  # type: ignore[arg-type]

    dense_results = retriever.search("alpha", mode="dense", top_k=2)
    sparse_results = retriever.search("beta", mode="sparse", top_k=2)
    hybrid_results = retriever.search("alpha", mode="hybrid", top_k=3)

    assert store.count() == 3
    assert dense_results[0].path == "tutorial/alpha.md"
    assert sparse_results[0].path == "advanced/beta.md"
    assert hybrid_results[0].path == "tutorial/alpha.md"


def test_filters_restrict_results(
    store: QdrantStore,
    dense_embedder: object,
    sparse_embedder: object,
) -> None:
    build_test_index(store, dense_embedder, sparse_embedder)
    retriever = Retriever(store, dense_embedder, sparse_embedder)  # type: ignore[arg-type]

    results = retriever.search(
        "alpha",
        mode="hybrid",
        top_k=5,
        filters=SearchFilters(section="advanced"),
    )

    assert results
    assert all(result.section == "advanced" for result in results)


def test_reindex_deletes_stale_points(
    store: QdrantStore,
    dense_embedder: object,
    sparse_embedder: object,
) -> None:
    build_test_index(store, dense_embedder, sparse_embedder)

    stats = build_index(
        chunks=[make_chunk("alpha", "alpha dependency injection", "tutorial/alpha.md")],
        store=store,
        dense=dense_embedder,  # type: ignore[arg-type]
        sparse=sparse_embedder,  # type: ignore[arg-type]
        version="v1",
        batch_size=1,
        recreate=False,
    )

    assert stats.points == 1
    assert stats.stale_deleted == 2
    assert store.count() == 1


def test_empty_sparse_query_falls_back_to_dense(
    store: QdrantStore,
    dense_embedder: object,
    sparse_embedder: object,
) -> None:
    build_test_index(store, dense_embedder, sparse_embedder)
    retriever = Retriever(store, dense_embedder, sparse_embedder)  # type: ignore[arg-type]

    results = retriever.search("unknown", mode="hybrid", top_k=3)

    assert len(results) == 3


def test_search_validates_input(
    store: QdrantStore,
    dense_embedder: object,
    sparse_embedder: object,
) -> None:
    retriever = Retriever(store, dense_embedder, sparse_embedder)  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        retriever.search("", mode="hybrid")
    with pytest.raises(ValueError):
        retriever.search("alpha", mode="hybrid", top_k=0)


def test_dimension_mismatch_requires_recreate(store: QdrantStore) -> None:
    store.ensure_collection(4, recreate=True)

    with pytest.raises(ValueError, match="dimension mismatch"):
        store.ensure_collection(8)


def test_corpus_version(
    store: QdrantStore,
    dense_embedder: object,
    sparse_embedder: object,
) -> None:
    build_test_index(store, dense_embedder, sparse_embedder)

    assert store.corpus_version() == "v1"
