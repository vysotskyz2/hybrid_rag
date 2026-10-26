from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from docs_rag import __version__
from docs_rag.config import Settings, get_settings
from docs_rag.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    configure_logging(settings.log_level, settings.log_format)
    yield


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    app = FastAPI(
        title=resolved.app_name,
        version=__version__,
        lifespan=lifespan,
    )
    app.state.settings = resolved

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {"name": resolved.app_name, "version": __version__}

    return app


app = create_app()
