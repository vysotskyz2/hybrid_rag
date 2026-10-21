import pytest

from docs_rag.config import Settings, get_settings


def test_settings_defaults() -> None:
    settings = Settings(_env_file=None)

    assert settings.app_name == "DocsLens"
    assert settings.qdrant_url == "http://localhost:6333"
    assert settings.retrieval_top_k == 5
    assert settings.llm_mode == "openrouter"
    assert settings.docs_ref == "68cc4cbb2e0600841b0d6bdd1cc29038b54a00e6"
    assert settings.chunk_max_tokens == 350


def test_settings_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_NAME", "Test App")
    monkeypatch.setenv("RETRIEVAL_TOP_K", "7")

    settings = Settings(_env_file=None)

    assert settings.app_name == "Test App"
    assert settings.retrieval_top_k == 7


def test_get_settings_is_cached() -> None:
    get_settings.cache_clear()

    assert get_settings() is get_settings()

    get_settings.cache_clear()
