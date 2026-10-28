from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from docs_rag import __version__
from docs_rag.api.deps import AppServices
from docs_rag.api.middleware import REQUEST_ID_HEADER, RequestContextMiddleware
from docs_rag.api.routes import router
from docs_rag.config import Settings, get_settings
from docs_rag.logging import configure_logging
from docs_rag.retrieval.embeddings import (
    FastEmbedSparseEmbedder,
    SentenceTransformerDenseEmbedder,
)
from docs_rag.retrieval.search import Retriever
from docs_rag.retrieval.store import QdrantStore

logger = structlog.get_logger(__name__)


def _build_services(settings: Settings) -> AppServices:
    dense = SentenceTransformerDenseEmbedder(
        model_name=settings.embedding_model,
        device=settings.embedding_device,
        batch_size=settings.embedding_batch_size,
        query_prefix=settings.dense_query_prefix,
        passage_prefix=settings.dense_passage_prefix,
        normalize=settings.normalize_embeddings,
    )
    sparse = FastEmbedSparseEmbedder(
        model_name=settings.sparse_model,
        language=settings.sparse_language,
        batch_size=settings.embedding_batch_size,
    )
    store = QdrantStore.from_settings(settings)
    try:
        retriever = Retriever(
            store=store,
            dense=dense,
            sparse=sparse,
            candidates=settings.retrieval_candidates,
        )
    except Exception:
        store.close()
        raise
    return AppServices(retriever=retriever, store=store)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = cast(Settings, app.state.settings)
    configure_logging(settings.log_level, settings.log_format)
    services = cast(AppServices | None, getattr(app.state, "services", None))
    if services is None:
        logger.info(
            "api_startup",
            collection=settings.qdrant_collection,
            dense_model=settings.embedding_model,
            sparse_model=settings.sparse_model,
        )
        services = _build_services(settings)
        app.state.services = services
    else:
        logger.info("api_startup", collection=services.store.collection, injected=True)

    try:
        yield
    finally:
        logger.info("api_shutdown")
        services.store.close()
        app.state.services = None


def create_app(
    settings: Settings | None = None,
    services: AppServices | None = None,
) -> FastAPI:
    resolved = settings or get_settings()
    app = FastAPI(
        title=resolved.app_name,
        version=__version__,
        lifespan=lifespan,
    )
    app.state.settings = resolved
    app.state.services = services

    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved.cors_origins),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[REQUEST_ID_HEADER],
    )
    app.include_router(router)

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {"name": resolved.app_name, "version": __version__}

    return app


app = create_app()
