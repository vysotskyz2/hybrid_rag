from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

from docs_rag.ingestion.models import Chunk
from docs_rag.retrieval.models import SparseVectorData


class FakeDenseEmbedder:
    dimension = 4

    def _vector(self, text: str) -> list[float]:
        lowered = text.casefold()
        return [
            1.0 if "alpha" in lowered else 0.0,
            1.0 if "beta" in lowered else 0.0,
            1.0 if "gamma" in lowered else 0.0,
            0.1,
        ]

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


class FakeSparseEmbedder:
    def _vector(self, text: str) -> SparseVectorData:
        lowered = text.casefold()
        indices: list[int] = []
        if "alpha" in lowered:
            indices.append(10)
        if "beta" in lowered:
            indices.append(20)
        if "gamma" in lowered:
            indices.append(30)
        return SparseVectorData(indices=indices, values=[1.0] * len(indices))

    def embed_documents(self, texts: Sequence[str]) -> list[SparseVectorData]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> SparseVectorData:
        return self._vector(text)


def make_chunk(
    chunk_id: str,
    text: str,
    path: str,
    section: str = "tutorial",
    content_type: str = "prose",
) -> Chunk:
    return Chunk(
        chunk_id=str(uuid5(NAMESPACE_URL, chunk_id)),
        doc_id=path,
        path=path,
        url=f"https://example.com/{path}",
        title=path,
        heading_path=f"Title > {chunk_id}",
        section=section,
        content_type=content_type,  # type: ignore[arg-type]
        language="en",
        project="fastapi",
        version="v1",
        chunk_index=0,
        content_hash=f"hash-{chunk_id}",
        text=text,
        token_count=len(text.split()),
    )
