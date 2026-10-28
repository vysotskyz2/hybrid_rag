from pathlib import Path

import pytest

from docs_rag.config import Settings, get_settings


def test_settings_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.app_name == "DocsLens"
    assert settings.qdrant_url == "http://localhost:6333"
    assert settings.retrieval_top_k == 5
    assert settings.llm_mode == "openrouter"
    assert settings.ingestion_config == Path("config/ingestion.toml")
    assert settings.log_format == "json"
    assert settings.dense_query_prefix == "query: "
    assert settings.dense_vector_name == "dense"
    assert settings.qdrant_distance == "cosine"
    assert settings.retrieval_default_mode == "hybrid"
    assert settings.payload_index_fields == (
        "section",
        "content_type",
        "language",
        "version",
        "path",
        "project",
    )
    assert settings.cors_origins == ("http://localhost:8501",)
    assert settings.ui_api_url == "http://localhost:8000"
    assert settings.search_max_top_k == 20
    assert settings.query_max_length == 500


def test_settings_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_NAME", "Test App")
    monkeypatch.setenv("RETRIEVAL_TOP_K", "7")
    monkeypatch.setenv("PAYLOAD_INDEX_FIELDS", '["section","version"]')
    monkeypatch.setenv("CORS_ORIGINS", '["https://ui.example"]')
    monkeypatch.setenv("UI_API_URL", "https://api.example")
    monkeypatch.setenv("SEARCH_MAX_TOP_K", "12")
    monkeypatch.setenv("QUERY_MAX_LENGTH", "300")

    settings = Settings(_env_file=None)

    assert settings.app_name == "Test App"
    assert settings.retrieval_top_k == 7
    assert settings.payload_index_fields == ("section", "version")
    assert settings.cors_origins == ("https://ui.example",)
    assert settings.ui_api_url == "https://api.example"
    assert settings.search_max_top_k == 12
    assert settings.query_max_length == 300


def test_get_settings_is_cached() -> None:
    get_settings.cache_clear()

    assert get_settings() is get_settings()

    get_settings.cache_clear()
