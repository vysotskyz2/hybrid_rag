from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Protocol, cast

from fastapi import Depends, HTTPException, Request, status

from docs_rag.config import Settings
from docs_rag.retrieval.models import SearchFilters, SearchMode, SearchResult


class SearchRetriever(Protocol):
    def search(
        self,
        query: str,
        mode: SearchMode = "hybrid",
        top_k: int = 5,
        filters: SearchFilters | None = None,
    ) -> list[SearchResult]: ...


class SearchStore(Protocol):
    @property
    def collection(self) -> str: ...

    @property
    def dense_vector_name(self) -> str: ...

    @property
    def sparse_vector_name(self) -> str: ...

    def count(self) -> int: ...

    def corpus_version(self) -> str | None: ...

    def close(self) -> None: ...


@dataclass(frozen=True, slots=True)
class AppServices:
    retriever: SearchRetriever
    store: SearchStore


def get_app_services(request: Request) -> AppServices:
    services = cast(AppServices | None, getattr(request.app.state, "services", None))
    if services is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Application services are not ready",
        )
    return services


def get_app_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


ServicesDep = Annotated[AppServices, Depends(get_app_services)]
SettingsDep = Annotated[Settings, Depends(get_app_settings)]
