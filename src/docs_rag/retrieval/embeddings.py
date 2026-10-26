from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Protocol, cast

from docs_rag.retrieval.models import SparseVectorData

if TYPE_CHECKING:
    from fastembed import SparseEmbedding
    from sentence_transformers import SentenceTransformer


class DenseEmbedder(Protocol):
    @property
    def dimension(self) -> int: ...

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class SparseEmbedder(Protocol):
    def embed_documents(self, texts: Sequence[str]) -> list[SparseVectorData]: ...

    def embed_query(self, text: str) -> SparseVectorData: ...


class SentenceTransformerDenseEmbedder:
    def __init__(
        self,
        model_name: str,
        device: str = "cpu",
        batch_size: int = 32,
        query_prefix: str = "query: ",
        passage_prefix: str = "passage: ",
        normalize: bool = True,
    ) -> None:
        from sentence_transformers import SentenceTransformer

        self._model: SentenceTransformer = SentenceTransformer(model_name, device=device)
        dimension = self._model.get_embedding_dimension()
        if dimension is None:
            raise ValueError(f"Embedding model has no dimension: {model_name}")
        self._dimension = int(dimension)
        self._batch_size = batch_size
        self._query_prefix = query_prefix
        self._passage_prefix = passage_prefix
        self._normalize = normalize

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return self._encode([f"{self._passage_prefix}{text}" for text in texts])

    def embed_query(self, text: str) -> list[float]:
        return self._encode([f"{self._query_prefix}{text}"])[0]

    def _encode(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._model.encode(
            texts,
            batch_size=self._batch_size,
            normalize_embeddings=self._normalize,
            show_progress_bar=False,
        )
        return cast(list[list[float]], vectors.tolist())


class FastEmbedSparseEmbedder:
    def __init__(
        self,
        model_name: str,
        language: str = "english",
        batch_size: int = 32,
    ) -> None:
        from fastembed import SparseTextEmbedding

        self._model = SparseTextEmbedding(model_name=model_name, language=language)
        self._batch_size = batch_size

    def embed_documents(self, texts: Sequence[str]) -> list[SparseVectorData]:
        if not texts:
            return []
        embeddings = self._model.embed(list(texts), batch_size=self._batch_size)
        return [self._to_data(embedding) for embedding in embeddings]

    def embed_query(self, text: str) -> SparseVectorData:
        return self.embed_documents([text])[0]

    @staticmethod
    def _to_data(embedding: SparseEmbedding) -> SparseVectorData:
        return SparseVectorData(
            indices=[int(index) for index in embedding.indices],
            values=[float(value) for value in embedding.values],
        )
