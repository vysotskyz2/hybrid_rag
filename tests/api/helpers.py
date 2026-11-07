from __future__ import annotations

from dataclasses import dataclass, field

from docs_rag.config import Settings
from docs_rag.generation.llm import FakeLLM
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


def make_search_result(
    chunk_id: str = "chunk-1",
    score: float = 0.9,
    retrieval_score: float | None = 0.5,
    path: str = "tutorial/dependencies.md",
    title: str = "Dependencies",
    heading_path: str = "Dependencies > Intro",
    text: str = "Dependency injection text",
    token_count: int = 10,
) -> SearchResult:
    return SearchResult(
        chunk_id=chunk_id,
        score=score,
        path=path,
        url=f"https://example.com/{path}",
        title=title,
        heading_path=heading_path,
        section="tutorial",
        content_type="prose",
        language="en",
        version="v1",
        token_count=token_count,
        text=text,
        retrieval_score=retrieval_score,
    )


@dataclass
class FakeSearchService:
    results: list[SearchResult] = field(default_factory=lambda: [make_search_result()])
    calls: list[tuple[str, SearchMode, int, SearchFilters | None, bool]] = field(
        default_factory=list
    )

    def search(
        self,
        query: str,
        mode: SearchMode = "hybrid",
        top_k: int = 5,
        filters: SearchFilters | None = None,
        rerank: bool = True,
    ) -> list[SearchResult]:
        self.calls.append((query, mode, top_k, filters, rerank))
        return self.results[:top_k]


class BrokenSearchService(FakeSearchService):
    def search(
        self,
        query: str,
        mode: SearchMode = "hybrid",
        top_k: int = 5,
        filters: SearchFilters | None = None,
        rerank: bool = True,
    ) -> list[SearchResult]:
        raise RuntimeError("retrieval backend is down")


class UnavailableLLM(FakeLLM):
    @property
    def available(self) -> bool:
        return False


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "search_max_top_k": 10,
        "query_max_length": 20,
        "cors_origins": ("http://localhost:8501",),
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[arg-type]
