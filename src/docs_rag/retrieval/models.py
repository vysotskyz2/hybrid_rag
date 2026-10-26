from dataclasses import asdict, dataclass
from typing import Literal

SearchMode = Literal["dense", "sparse", "hybrid"]


@dataclass(frozen=True, slots=True)
class SparseVectorData:
    indices: list[int]
    values: list[float]


@dataclass(frozen=True, slots=True)
class SearchFilters:
    section: str | None = None
    content_type: str | None = None
    language: str | None = None
    version: str | None = None
    path: str | None = None


@dataclass(frozen=True, slots=True)
class SearchResult:
    chunk_id: str
    score: float
    path: str
    url: str
    title: str
    heading_path: str
    section: str
    content_type: str
    language: str
    version: str
    token_count: int
    text: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
