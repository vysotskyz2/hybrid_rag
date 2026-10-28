from fastapi.testclient import TestClient

from docs_rag.api.deps import AppServices
from docs_rag.api.main import create_app
from docs_rag.config import Settings
from tests.api.helpers import FakeRetriever, FakeStore


def test_stats(client: TestClient) -> None:
    response = client.get("/api/stats")

    assert response.status_code == 200
    assert response.json() == {
        "collection": "test",
        "points": 3,
        "version": "v1",
        "vectors": ["dense", "sparse"],
    }


def test_stats_with_empty_collection(settings: Settings) -> None:
    app = create_app(
        settings,
        AppServices(retriever=FakeRetriever(), store=FakeStore(points=0, version=None)),
    )

    with TestClient(app) as client:
        response = client.get("/api/stats")

    assert response.status_code == 200
    assert response.json()["points"] == 0
    assert response.json()["version"] is None


def test_stats_when_qdrant_is_unavailable(settings: Settings) -> None:
    app = create_app(
        settings,
        AppServices(retriever=FakeRetriever(), store=FakeStore(fail=True)),
    )

    with TestClient(app) as client:
        response = client.get("/api/stats")

    assert response.status_code == 503
    assert response.json() == {"detail": "Index statistics are unavailable"}
