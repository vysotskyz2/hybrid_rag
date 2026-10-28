from __future__ import annotations

from dataclasses import dataclass, field

from docs_rag.config import Settings
from docs_rag.retrieval.models import SearchFilters, SearchMode, SearchResult


@dataclass
class FakeStore:
    points: int = 3
    version: str | None = "v1"
    fail: bool = False
    closed: bool = False
    collection: str = "test"
    dense_vector_name: str = "dense"
    sparse_vector_name: str = "sparse"

    def count(self) -> int:
        if self.fail:
            raise RuntimeError("qdrant is down")
        return self.points

    def corpus_version(self) -> str | None:
        if self.fail:
            raise RuntimeError("qdrant is down")
        return self.version

    def close(self) -> None:
        self.closed = True


@dataclass
class FakeRetriever:
    calls: list[tuple[str, SearchMode, int, SearchFilters | None]] = field(default_factory=list)

    def search(
        self,
        query: str,
        mode: SearchMode = "hybrid",
        top_k: int = 5,
        filters: SearchFilters | None = None,
    ) -> list[SearchResult]:
        self.calls.append((query, mode, top_k, filters))
        return [
            SearchResult(
                chunk_id="chunk-1",
                score=0.9,
                path="tutorial/dependencies.md",
                url="https://example.com/tutorial/dependencies",
                title="Dependencies",
                heading_path="Dependencies > Intro",
                section="tutorial",
                content_type="prose",
                language="en",
                version="v1",
                token_count=10,
                text="Dependency injection text",
            )
        ]


class BrokenRetriever(FakeRetriever):
    def search(
        self,
        query: str,
        mode: SearchMode = "hybrid",
        top_k: int = 5,
        filters: SearchFilters | None = None,
    ) -> list[SearchResult]:
        raise RuntimeError("retrieval backend is down")


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "search_max_top_k": 10,
        "query_max_length": 20,
        "cors_origins": ("http://localhost:8501",),
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[arg-type]
