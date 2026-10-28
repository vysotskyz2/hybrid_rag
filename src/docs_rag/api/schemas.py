from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from docs_rag.retrieval.models import SearchMode, SearchResult

ContentType = Literal["prose", "code", "mixed"]


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    mode: SearchMode | None = None
    top_k: int | None = Field(default=None, ge=1)
    section: str | None = None
    content_type: ContentType | None = None
    language: str | None = None
    version: str | None = None

    @field_validator("query")
    @classmethod
    def _validate_query(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("query must not be empty")
        return stripped


class SearchResultSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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

    @classmethod
    def from_result(cls, result: SearchResult) -> SearchResultSchema:
        return cls.model_validate(result)


class SearchResponse(BaseModel):
    query: str
    mode: SearchMode
    top_k: int
    results: list[SearchResultSchema]


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ReadyResponse(BaseModel):
    status: Literal["ready"] = "ready"
    collection: str
    points: int


class StatsResponse(BaseModel):
    collection: str
    points: int
    version: str | None
    vectors: list[str]


class ErrorResponse(BaseModel):
    detail: str
    reason: str | None = None
