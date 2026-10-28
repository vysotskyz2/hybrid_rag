from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from docs_rag.api.deps import AppServices
from docs_rag.api.main import create_app
from docs_rag.config import Settings
from tests.api.helpers import FakeRetriever, FakeStore, make_settings


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
def fake_store() -> FakeStore:
    return FakeStore()


@pytest.fixture
def fake_retriever() -> FakeRetriever:
    return FakeRetriever()


@pytest.fixture
def client(
    settings: Settings,
    fake_store: FakeStore,
    fake_retriever: FakeRetriever,
) -> Iterator[TestClient]:
    app = create_app(
        settings,
        AppServices(retriever=fake_retriever, store=fake_store),
    )
    with TestClient(app) as test_client:
        yield test_client
