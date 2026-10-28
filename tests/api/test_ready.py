from fastapi.testclient import TestClient

from docs_rag.api.deps import AppServices
from docs_rag.api.main import create_app
from docs_rag.config import Settings
from tests.api.helpers import FakeRetriever, FakeStore


def test_ready(client: TestClient) -> None:
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "collection": "test",
        "points": 3,
    }


def test_ready_with_empty_collection(settings: Settings) -> None:
    app = create_app(
        settings,
        AppServices(retriever=FakeRetriever(), store=FakeStore(points=0)),
    )

    with TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Index is not ready",
        "reason": "Collection is empty",
    }


def test_ready_when_qdrant_is_unavailable(settings: Settings) -> None:
    app = create_app(
        settings,
        AppServices(retriever=FakeRetriever(), store=FakeStore(fail=True)),
    )

    with TestClient(app) as client:
        response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Index is not ready",
        "reason": "Qdrant is unavailable or the collection is missing",
    }
