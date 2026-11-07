from __future__ import annotations

import time
from collections.abc import AsyncIterator
from dataclasses import dataclass

import structlog
from fastapi import APIRouter, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, StreamingResponse

from docs_rag.api.deps import ServicesDep, SettingsDep
from docs_rag.api.schemas import (
    AskRequest,
    ErrorResponse,
    HealthResponse,
    ReadyResponse,
    SearchRequest,
    SearchResponse,
    SearchResultSchema,
    SourceSchema,
    StatsResponse,
)
from docs_rag.api.sse import SSE_HEADERS, format_event
from docs_rag.config import Settings
from docs_rag.generation.llm import LLMError
from docs_rag.generation.prompt import NO_CONTEXT_ANSWER, build_prompt
from docs_rag.retrieval.models import SearchFilters, SearchMode

logger = structlog.get_logger(__name__)

router = APIRouter()


@dataclass(frozen=True, slots=True)
class _SearchParams:
    query: str
    mode: SearchMode
    top_k: int
    filters: SearchFilters


def _resolve_search_params(payload: SearchRequest, settings: Settings) -> _SearchParams:
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
    return _SearchParams(
        query=query,
        mode=mode,
        top_k=top_k,
        filters=SearchFilters(
            section=payload.section,
            content_type=payload.content_type,
            language=payload.language,
            version=payload.version,
        ),
    )


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
    params = _resolve_search_params(payload, settings)

    started = time.perf_counter()
    try:
        results = await run_in_threadpool(
            services.search.search,
            query=params.query,
            mode=params.mode,
            top_k=params.top_k,
            filters=params.filters,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("search_failed", mode=params.mode, top_k=params.top_k)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search is temporarily unavailable",
        ) from exc

    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    reranked = any(result.retrieval_score is not None for result in results)
    logger.info(
        "search_completed",
        mode=params.mode,
        top_k=params.top_k,
        results=len(results),
        reranked=reranked,
        duration_ms=duration_ms,
        query_length=len(params.query),
    )
    return SearchResponse(
        query=params.query,
        mode=params.mode,
        top_k=params.top_k,
        reranked=reranked,
        results=[SearchResultSchema.from_result(result) for result in results],
    )


@router.post(
    "/api/ask",
    tags=["ask"],
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
    },
)
async def ask(
    payload: AskRequest,
    services: ServicesDep,
    settings: SettingsDep,
) -> StreamingResponse:
    if not services.llm.available:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM is not configured. Set LLM_API_KEY or use LLM_MODE=fake.",
        )

    params = _resolve_search_params(payload, settings)
    started = time.perf_counter()

    try:
        results = await run_in_threadpool(
            services.search.search,
            query=params.query,
            mode=params.mode,
            top_k=params.top_k,
            filters=params.filters,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("ask_search_failed", mode=params.mode, top_k=params.top_k)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search is temporarily unavailable",
        ) from exc

    reranked = any(result.retrieval_score is not None for result in results)
    prompt = build_prompt(params.query, results, settings.llm_context_max_tokens)
    logger.info(
        "ask_started",
        mode=params.mode,
        top_k=params.top_k,
        retrieved=len(results),
        selected=len(prompt.sources) if prompt else 0,
        reranked=reranked,
    )

    if prompt is None:

        async def no_context_events() -> AsyncIterator[str]:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            yield format_event("sources", {"sources": []})
            yield format_event("token", {"text": NO_CONTEXT_ANSWER})
            yield format_event(
                "done",
                {
                    "model": services.llm.model,
                    "sources": 0,
                    "reranked": reranked,
                    "duration_ms": duration_ms,
                },
            )
            logger.info(
                "ask_completed",
                mode=params.mode,
                sources=0,
                reranked=reranked,
                duration_ms=duration_ms,
            )

        return StreamingResponse(
            no_context_events(),
            media_type="text/event-stream",
            headers=SSE_HEADERS,
        )

    prompt_bundle = prompt
    sources = [
        SourceSchema.from_source(result, index)
        for index, result in enumerate(prompt_bundle.sources, start=1)
    ]
    source_payload = [source.model_dump() for source in sources]
    source_count = len(sources)

    async def events() -> AsyncIterator[str]:
        yield format_event("sources", {"sources": source_payload})
        try:
            async for token in services.llm.stream_chat(prompt_bundle.messages):
                yield format_event("token", {"text": token})
        except LLMError as exc:
            logger.warning("ask_stream_failed", error=str(exc), sources=source_count)
            yield format_event(
                "error",
                {"detail": "LLM generation failed", "code": "llm_error"},
            )
            return
        except Exception:
            logger.exception("ask_stream_failed", sources=source_count)
            yield format_event(
                "error",
                {"detail": "Generation failed", "code": "internal_error"},
            )
            return

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.info(
            "ask_completed",
            mode=params.mode,
            sources=source_count,
            reranked=reranked,
            duration_ms=duration_ms,
        )
        yield format_event(
            "done",
            {
                "model": services.llm.model,
                "sources": source_count,
                "reranked": reranked,
                "duration_ms": duration_ms,
            },
        )

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
