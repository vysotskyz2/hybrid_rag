from __future__ import annotations

import time

import structlog
from fastapi import APIRouter, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from docs_rag.api.deps import ServicesDep, SettingsDep
from docs_rag.api.schemas import (
    ErrorResponse,
    HealthResponse,
    ReadyResponse,
    SearchRequest,
    SearchResponse,
    SearchResultSchema,
    StatsResponse,
)
from docs_rag.retrieval.models import SearchFilters

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    return HealthResponse()


@router.get(
    "/ready",
    response_model=ReadyResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse}},
    tags=["system"],
)
async def ready(services: ServicesDep) -> ReadyResponse | JSONResponse:
    try:
        points = await run_in_threadpool(services.store.count)
    except Exception as exc:
        logger.warning("readiness_check_failed", error=str(exc))
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "detail": "Index is not ready",
                "reason": "Qdrant is unavailable or the collection is missing",
            },
        )
    if points <= 0:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "detail": "Index is not ready",
                "reason": "Collection is empty",
            },
        )
    return ReadyResponse(collection=services.store.collection, points=points)


@router.get(
    "/api/stats",
    response_model=StatsResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse}},
    tags=["system"],
)
async def stats(services: ServicesDep) -> StatsResponse:
    try:
        points = await run_in_threadpool(services.store.count)
        version = await run_in_threadpool(services.store.corpus_version)
    except Exception as exc:
        logger.warning("stats_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Index statistics are unavailable",
        ) from exc
    return StatsResponse(
        collection=services.store.collection,
        points=points,
        version=version,
        vectors=[services.store.dense_vector_name, services.store.sparse_vector_name],
    )


@router.post("/api/search", response_model=SearchResponse, tags=["search"])
async def search(
    payload: SearchRequest,
    services: ServicesDep,
    settings: SettingsDep,
) -> SearchResponse:
    query = payload.query.strip()
    if len(query) > settings.query_max_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Query is too long: maximum {settings.query_max_length} characters",
        )

    top_k = payload.top_k or min(settings.retrieval_top_k, settings.search_max_top_k)
    if top_k > settings.search_max_top_k:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"top_k must not exceed {settings.search_max_top_k}",
        )

    mode = payload.mode or settings.retrieval_default_mode
    filters = SearchFilters(
        section=payload.section,
        content_type=payload.content_type,
        language=payload.language,
        version=payload.version,
    )

    started = time.perf_counter()
    try:
        results = await run_in_threadpool(
            services.retriever.search,
            query=query,
            mode=mode,
            top_k=top_k,
            filters=filters,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("search_failed", mode=mode, top_k=top_k)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search is temporarily unavailable",
        ) from exc

    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    logger.info(
        "search_completed",
        mode=mode,
        top_k=top_k,
        results=len(results),
        duration_ms=duration_ms,
        query_length=len(query),
    )
    return SearchResponse(
        query=query,
        mode=mode,
        top_k=top_k,
        results=[SearchResultSchema.from_result(result) for result in results],
    )
