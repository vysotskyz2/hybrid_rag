from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
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

    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: SecretStr | None = None
    qdrant_collection: str = "fastapi_docs"

    docs_repo: str = "fastapi/fastapi"
    docs_ref: str = "68cc4cbb2e0600841b0d6bdd1cc29038b54a00e6"
    docs_base_url: str = "https://fastapi.tiangolo.com"
    docs_source_path: str = "docs/en/docs"
    docs_language: str = "en"
    data_dir: Path = Path("data")
    chunk_target_tokens: int = 280
    chunk_max_tokens: int = 350
    chunk_overlap_tokens: int = 50

    embedding_model: str = "intfloat/multilingual-e5-base"
    embedding_device: str = "cpu"
    embedding_batch_size: int = 32
    sparse_model: str = "Qdrant/bm25"
    sparse_language: str = "english"

    retrieval_candidates: int = 30
    retrieval_top_k: int = 5
    rerank_enabled: bool = True
    rerank_model: str = "BAAI/bge-reranker-v2-m3"

    llm_mode: Literal["openrouter", "fake"] = "openrouter"
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_api_key: SecretStr | None = None
    llm_model: str = "deepseek/deepseek-chat"


@lru_cache
def get_settings() -> Settings:
    return Settings()
