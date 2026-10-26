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
    ) -> None:
        from sentence_transformers import SentenceTransformer

        self._model: SentenceTransformer = SentenceTransformer(model_name, device=device)
        dimension = self._model.get_embedding_dimension()
        if dimension is None:
            raise ValueError(f"Embedding model has no dimension: {model_name}")
        self._dimension = int(dimension)
        self._batch_size = batch_size

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return self._encode([f"passage: {text}" for text in texts])

    def embed_query(self, text: str) -> list[float]:
        return self._encode([f"query: {text}"])[0]

    def _encode(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._model.encode(
            texts,
            batch_size=self._batch_size,
            normalize_embeddings=True,
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
