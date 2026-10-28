from fastapi.testclient import TestClient

from docs_rag.api.deps import AppServices
from docs_rag.api.main import create_app
from docs_rag.config import Settings
from tests.api.helpers import FakeRetriever, FakeStore


def test_health(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["name"] == "DocsLens"
    assert response.json()["version"] == "0.1.0"


def test_shutdown_closes_store(settings: Settings) -> None:
    store = FakeStore()
    retriever = FakeRetriever()
    app = create_app(settings, AppServices(retriever=retriever, store=store))

    with TestClient(app):
        pass

    assert store.closed is True
    assert app.state.services is None
