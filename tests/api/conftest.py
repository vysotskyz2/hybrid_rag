from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from docs_rag.api.deps import AppServices
from docs_rag.api.main import create_app
from docs_rag.config import Settings
from docs_rag.generation.llm import FakeLLM
from tests.api.helpers import FakeSearchService, FakeStore, make_settings


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
def fake_store() -> FakeStore:
    return FakeStore()


@pytest.fixture
def fake_search() -> FakeSearchService:
    return FakeSearchService()


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def client(
    settings: Settings,
    fake_store: FakeStore,
    fake_search: FakeSearchService,
    fake_llm: FakeLLM,
) -> Iterator[TestClient]:
    app = create_app(
        settings,
        AppServices(search=fake_search, store=fake_store, llm=fake_llm),
    )
    with TestClient(app) as test_client:
        yield test_client
