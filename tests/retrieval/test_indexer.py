import json
from pathlib import Path

import pytest

from docs_rag.retrieval.indexer import build_index, load_chunks
from docs_rag.retrieval.store import QdrantStore
from tests.retrieval.helpers import make_chunk


def test_load_chunks_reads_jsonl(tmp_path: Path) -> None:
    path = tmp_path / "chunks.jsonl"
    chunk = make_chunk("alpha", "alpha text", "tutorial/alpha.md")
    path.write_text(json.dumps(chunk.to_dict()) + "\n", encoding="utf-8")

    chunks = load_chunks(path)

    assert len(chunks) == 1
    assert chunks[0].chunk_id == chunk.chunk_id
    assert chunks[0].text == "alpha text"


def test_build_index_rejects_empty_chunks(store: QdrantStore) -> None:
    with pytest.raises(ValueError, match="No chunks"):
        build_index(
            chunks=[],
            store=store,
            dense=None,  # type: ignore[arg-type]
            sparse=None,  # type: ignore[arg-type]
            version="v1",
        )


def test_build_index_rejects_non_positive_batch(
    store: QdrantStore,
    dense_embedder: object,
    sparse_embedder: object,
) -> None:
    with pytest.raises(ValueError, match="batch_size"):
        build_index(
            chunks=[make_chunk("alpha", "alpha", "tutorial/alpha.md")],
            store=store,
            dense=dense_embedder,  # type: ignore[arg-type]
            sparse=sparse_embedder,  # type: ignore[arg-type]
            version="v1",
            batch_size=0,
        )
