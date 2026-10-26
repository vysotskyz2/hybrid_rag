import os
from pathlib import Path

import pytest

from docs_rag.config import Settings
from docs_rag.retrieval.embeddings import (
    FastEmbedSparseEmbedder,
    SentenceTransformerDenseEmbedder,
)
from docs_rag.retrieval.indexer import build_index, load_chunks
from docs_rag.retrieval.search import Retriever
from docs_rag.retrieval.store import QdrantStore

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_INTEGRATION") != "1",
        reason="set RUN_INTEGRATION=1 to load embedding models",
    ),
]


def test_real_models_retrieve_dependency_docs() -> None:
    chunks_path = Path("data/chunks/chunks.jsonl")
    if not chunks_path.exists():
        pytest.skip("run `uv run docs-rag ingest` first")

    settings = Settings(_env_file=None)
    chunks = [
        chunk
        for chunk in load_chunks(chunks_path)
        if "dependencies" in chunk.path or "security" in chunk.path
    ][:80]
    dense = SentenceTransformerDenseEmbedder(
        model_name=settings.embedding_model,
        device=settings.embedding_device,
        batch_size=settings.embedding_batch_size,
    )
    sparse = FastEmbedSparseEmbedder(
        model_name=settings.sparse_model,
        language=settings.sparse_language,
    )
    store = QdrantStore.in_memory("integration")
    try:
        build_index(
            chunks=chunks,
            store=store,
            dense=dense,
            sparse=sparse,
            version=chunks[0].version,
            batch_size=16,
            recreate=True,
        )
        retriever = Retriever(store, dense, sparse)
        results = retriever.search(
            "How do I use Depends for dependency injection?",
            mode="hybrid",
            top_k=5,
        )
        assert results
        assert any("dependencies" in result.path for result in results)
        assert any(
            "depend" in result.text.casefold() or "depend" in result.heading_path.casefold()
            for result in results
        )
    finally:
        store.close()
