from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import structlog
from qdrant_client import models

from docs_rag.ingestion.models import Chunk
from docs_rag.retrieval.embeddings import DenseEmbedder, SparseEmbedder
from docs_rag.retrieval.store import QdrantStore

logger = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class IndexStats:
    chunks: int
    points: int
    dense_dimension: int
    collection: str
    created: bool
    stale_deleted: int
    elapsed_seconds: float

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def load_chunks(path: Path) -> list[Chunk]:
    chunks: list[Chunk] = []
    with path.open("r", encoding="utf-8") as source:
        for line in source:
            line = line.strip()
            if line:
                chunks.append(Chunk(**json.loads(line)))
    return chunks


def build_index(
    chunks: list[Chunk],
    store: QdrantStore,
    dense: DenseEmbedder,
    sparse: SparseEmbedder,
    version: str,
    batch_size: int = 32,
    recreate: bool = False,
) -> IndexStats:
    if not chunks:
        raise ValueError("No chunks to index")
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")

    started = time.perf_counter()
    created = store.ensure_collection(dense.dimension, recreate=recreate)

    for offset in range(0, len(chunks), batch_size):
        batch = chunks[offset : offset + batch_size]
        texts = [chunk.text for chunk in batch]
        dense_vectors = dense.embed_documents(texts)
        sparse_vectors = sparse.embed_documents(texts)

        points: list[models.PointStruct] = []
        for chunk, dense_vector, sparse_vector in zip(
            batch,
            dense_vectors,
            sparse_vectors,
            strict=True,
        ):
            vector: dict[str, Any] = {store.dense_vector_name: dense_vector}
            if sparse_vector.indices:
                vector[store.sparse_vector_name] = models.SparseVector(
                    indices=sparse_vector.indices,
                    values=sparse_vector.values,
                )
            points.append(
                models.PointStruct(
                    id=chunk.chunk_id,
                    vector=vector,
                    payload=chunk.to_dict(),
                )
            )

        store.upsert(points)
        logger.info(
            "index_batch",
            done=min(offset + len(batch), len(chunks)),
            total=len(chunks),
        )

    stale_deleted = store.delete_stale(
        version=version,
        keep_ids={chunk.chunk_id for chunk in chunks},
    )
    point_count = store.count()
    elapsed = time.perf_counter() - started

    logger.info(
        "index_built",
        chunks=len(chunks),
        points=point_count,
        collection=store.collection,
        elapsed_seconds=round(elapsed, 2),
    )
    return IndexStats(
        chunks=len(chunks),
        points=point_count,
        dense_dimension=dense.dimension,
        collection=store.collection,
        created=created,
        stale_deleted=stale_deleted,
        elapsed_seconds=round(elapsed, 2),
    )
