from collections.abc import Iterator

import pytest

from docs_rag.retrieval.store import QdrantStore
from tests.retrieval.helpers import FakeDenseEmbedder, FakeSparseEmbedder


@pytest.fixture
def dense_embedder() -> FakeDenseEmbedder:
    return FakeDenseEmbedder()


@pytest.fixture
def sparse_embedder() -> FakeSparseEmbedder:
    return FakeSparseEmbedder()


@pytest.fixture
def store() -> Iterator[QdrantStore]:
    instance = QdrantStore.in_memory("test")
    try:
        yield instance
    finally:
        instance.close()
