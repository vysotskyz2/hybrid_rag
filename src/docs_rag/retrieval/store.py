from __future__ import annotations

from typing import Any

import structlog
from qdrant_client import QdrantClient, models

from docs_rag.config import Settings
from docs_rag.retrieval.filters import build_qdrant_filter
from docs_rag.retrieval.models import SearchFilters, SparseVectorData

logger = structlog.get_logger(__name__)

DENSE_VECTOR = "dense"
SPARSE_VECTOR = "sparse"
PAYLOAD_INDEX_FIELDS = (
    "section",
    "content_type",
    "language",
    "version",
    "path",
    "project",
)


class QdrantStore:
    def __init__(
        self,
        client: QdrantClient,
        collection: str,
        dense_vector_name: str = DENSE_VECTOR,
        sparse_vector_name: str = SPARSE_VECTOR,
        distance: str = "cosine",
        payload_index_fields: tuple[str, ...] = PAYLOAD_INDEX_FIELDS,
        local: bool = False,
    ) -> None:
        self._client = client
        self._collection = collection
        self._dense_vector_name = dense_vector_name
        self._sparse_vector_name = sparse_vector_name
        self._distance = distance
        self._payload_index_fields = payload_index_fields
        self._local = local

    @classmethod
    def from_settings(cls, settings: Settings) -> QdrantStore:
        api_key = settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None
        client = QdrantClient(
            url=settings.qdrant_url,
            api_key=api_key or None,
            timeout=settings.qdrant_timeout,
        )
        return cls(
            client,
            settings.qdrant_collection,
            dense_vector_name=settings.dense_vector_name,
            sparse_vector_name=settings.sparse_vector_name,
            distance=settings.qdrant_distance,
            payload_index_fields=settings.payload_index_fields,
        )

    @classmethod
    def in_memory(cls, collection: str = "test") -> QdrantStore:
        return cls(QdrantClient(":memory:"), collection, local=True)

    @property
    def collection(self) -> str:
        return self._collection

    @property
    def dense_vector_name(self) -> str:
        return self._dense_vector_name

    @property
    def sparse_vector_name(self) -> str:
        return self._sparse_vector_name

    def ensure_collection(self, dense_dimension: int, recreate: bool = False) -> bool:
        existing = {item.name for item in self._client.get_collections().collections}

        if self._collection in existing and recreate:
            self._client.delete_collection(self._collection)
            existing.remove(self._collection)

        if self._collection not in existing:
            self._client.create_collection(
                collection_name=self._collection,
                vectors_config={
                    self._dense_vector_name: models.VectorParams(
                        size=dense_dimension,
                        distance=self._resolve_distance(),
                    )
                },
                sparse_vectors_config={
                    self._sparse_vector_name: models.SparseVectorParams(
                        modifier=models.Modifier.IDF,
                    )
                },
            )
            self._create_payload_indexes()
            return True

        info = self._client.get_collection(self._collection)
        vectors = info.config.params.vectors
        if not isinstance(vectors, dict) or self._dense_vector_name not in vectors:
            raise ValueError(
                f"Collection {self._collection!r} has no {self._dense_vector_name!r} vector"
            )

        params = vectors[self._dense_vector_name]
        if params.size != dense_dimension:
            raise ValueError(
                "Embedding dimension mismatch: "
                f"collection={params.size}, model={dense_dimension}. Use --recreate."
            )
        return False

    def _resolve_distance(self) -> models.Distance:
        distances = {
            "cosine": models.Distance.COSINE,
            "dot": models.Distance.DOT,
            "euclid": models.Distance.EUCLID,
        }
        try:
            return distances[self._distance]
        except KeyError as error:
            raise ValueError(f"Unsupported distance: {self._distance}") from error

    def _create_payload_indexes(self) -> None:
        if self._local:
            return
        for field_name in self._payload_index_fields:
            self._client.create_payload_index(
                collection_name=self._collection,
                field_name=field_name,
                field_schema=models.PayloadSchemaType.KEYWORD,
                wait=True,
            )

    def upsert(self, points: list[models.PointStruct]) -> None:
        self._client.upsert(
            collection_name=self._collection,
            points=points,
            wait=True,
        )

    def search_dense(
        self,
        query_vector: list[float],
        limit: int,
        filters: SearchFilters | None = None,
    ) -> list[models.ScoredPoint]:
        response = self._client.query_points(
            collection_name=self._collection,
            query=query_vector,
            using=self._dense_vector_name,
            query_filter=build_qdrant_filter(filters),
            limit=limit,
            with_payload=True,
        )
        return list(response.points)

    def search_sparse(
        self,
        query_vector: SparseVectorData,
        limit: int,
        filters: SearchFilters | None = None,
    ) -> list[models.ScoredPoint]:
        if not query_vector.indices:
            return []

        response = self._client.query_points(
            collection_name=self._collection,
            query=models.SparseVector(
                indices=query_vector.indices,
                values=query_vector.values,
            ),
            using=self._sparse_vector_name,
            query_filter=build_qdrant_filter(filters),
            limit=limit,
            with_payload=True,
        )
        return list(response.points)

    def search_hybrid(
        self,
        dense_vector: list[float],
        sparse_vector: SparseVectorData,
        limit: int,
        candidates: int,
        filters: SearchFilters | None = None,
    ) -> list[models.ScoredPoint]:
        qdrant_filter = build_qdrant_filter(filters)
        prefetch = [
            models.Prefetch(
                query=dense_vector,
                using=self._dense_vector_name,
                limit=candidates,
                filter=qdrant_filter,
            )
        ]
        if sparse_vector.indices:
            prefetch.append(
                models.Prefetch(
                    query=models.SparseVector(
                        indices=sparse_vector.indices,
                        values=sparse_vector.values,
                    ),
                    using=self._sparse_vector_name,
                    limit=candidates,
                    filter=qdrant_filter,
                )
            )

        if len(prefetch) == 1:
            return self.search_dense(dense_vector, limit, filters)

        response = self._client.query_points(
            collection_name=self._collection,
            prefetch=prefetch,
            query=models.RrfQuery(rrf=models.Rrf()),
            limit=limit,
            with_payload=True,
        )
        return list(response.points)

    def delete_stale(self, version: str, keep_ids: set[str]) -> int:
        version_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="version",
                    match=models.MatchValue(value=version),
                )
            ]
        )

        existing: set[str] = set()
        offset: Any = None
        while True:
            records, offset = self._client.scroll(
                collection_name=self._collection,
                scroll_filter=version_filter,
                limit=256,
                offset=offset,
                with_payload=False,
                with_vectors=False,
            )
            existing.update(str(record.id) for record in records)
            if offset is None:
                break

        stale = sorted(existing - keep_ids)
        if stale:
            self._client.delete(
                collection_name=self._collection,
                points_selector=models.PointIdsList(points=stale),
                wait=True,
            )
            logger.info("stale_points_deleted", count=len(stale))
        return len(stale)

    def count(self) -> int:
        return self._client.count(
            collection_name=self._collection,
            exact=True,
        ).count

    def close(self) -> None:
        self._client.close()
