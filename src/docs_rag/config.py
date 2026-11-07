from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    app_name: str = "DocsLens"
    environment: Literal["local", "test", "production"] = "local"
    log_level: str = "INFO"
    log_format: Literal["json", "console"] = "json"
    data_dir: Path = Path("data")
    ingestion_config: Path = Path("config/ingestion.toml")
    docs_archive_url_template: str = "https://github.com/{repo}/archive/{ref}.tar.gz"
    download_timeout: int = 120

    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: SecretStr | None = None
    qdrant_collection: str = "fastapi_docs"
    qdrant_timeout: int = 30
    qdrant_distance: Literal["cosine", "dot", "euclid"] = "cosine"
    dense_vector_name: str = "dense"
    sparse_vector_name: str = "sparse"
    payload_index_fields: tuple[str, ...] = (
        "section",
        "content_type",
        "language",
        "version",
        "path",
        "project",
    )
    index_batch_size: int = 32

    embedding_model: str = "intfloat/multilingual-e5-base"
    embedding_device: str = "cpu"
    embedding_batch_size: int = 32
    dense_query_prefix: str = "query: "
    dense_passage_prefix: str = "passage: "
    normalize_embeddings: bool = True
    sparse_model: str = "Qdrant/bm25"
    sparse_language: str = "english"

    retrieval_candidates: int = 30
    retrieval_top_k: int = 5
    retrieval_default_mode: Literal["dense", "sparse", "hybrid"] = "hybrid"
    rerank_enabled: bool = True
    rerank_model: str = "BAAI/bge-reranker-v2-m3"
    rerank_candidates: int = Field(default=10, ge=1)
    rerank_batch_size: int = Field(default=8, ge=1)
    rerank_max_length: int = Field(default=512, ge=1)

    llm_mode: Literal["openrouter", "fake"] = "openrouter"
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_api_key: SecretStr | None = None
    llm_model: str = "deepseek/deepseek-chat"
    llm_temperature: float = Field(default=0.2, ge=0, le=2)
    llm_max_tokens: int = Field(default=800, ge=1)
    llm_context_max_tokens: int = Field(default=4000, ge=1)
    llm_timeout: int = Field(default=120, ge=1)

    cors_origins: tuple[str, ...] = ("http://localhost:8501",)
    ui_api_url: str = "http://localhost:8000"
    search_max_top_k: int = Field(default=20, ge=1)
    query_max_length: int = Field(default=500, ge=1)


@lru_cache
def get_settings() -> Settings:
    return Settings()
