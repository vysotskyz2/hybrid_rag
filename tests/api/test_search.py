import pytest
from fastapi.testclient import TestClient

from docs_rag.api.deps import AppServices
from docs_rag.api.main import create_app
from docs_rag.config import Settings
from docs_rag.retrieval.models import SearchFilters
from tests.api.helpers import BrokenRetriever, FakeRetriever, FakeStore


def test_search_defaults(client: TestClient, fake_retriever: FakeRetriever) -> None:
    response = client.post("/api/search", json={"query": "Depends"})

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "Depends"
    assert body["mode"] == "hybrid"
    assert body["top_k"] == 5
    assert body["results"][0]["chunk_id"] == "chunk-1"
    assert body["results"][0]["text"] == "Dependency injection text"
    assert fake_retriever.calls == [("Depends", "hybrid", 5, SearchFilters())]


@pytest.mark.parametrize("mode", ["dense", "sparse", "hybrid"])
def test_search_modes(
    client: TestClient,
    fake_retriever: FakeRetriever,
    mode: str,
) -> None:
    response = client.post(
        "/api/search",
        json={"query": "alpha", "mode": mode, "top_k": 3},
    )

    assert response.status_code == 200
    assert response.json()["mode"] == mode
    assert response.json()["top_k"] == 3
    assert fake_retriever.calls[0][1] == mode


def test_search_passes_filters(client: TestClient, fake_retriever: FakeRetriever) -> None:
    response = client.post(
        "/api/search",
        json={
            "query": "Depends",
            "section": "tutorial",
            "content_type": "prose",
            "language": "en",
            "version": "v1",
        },
    )

    assert response.status_code == 200
    assert fake_retriever.calls[0][3] == SearchFilters(
        section="tutorial",
        content_type="prose",
        language="en",
        version="v1",
    )


def test_search_strips_query(client: TestClient, fake_retriever: FakeRetriever) -> None:
    response = client.post("/api/search", json={"query": "  Depends  "})

    assert response.status_code == 200
    assert response.json()["query"] == "Depends"
    assert fake_retriever.calls[0][0] == "Depends"


@pytest.mark.parametrize("query", ["", "   "])
def test_search_rejects_empty_query(client: TestClient, query: str) -> None:
    response = client.post("/api/search", json={"query": query})

    assert response.status_code == 422


def test_search_rejects_unknown_mode(client: TestClient) -> None:
    response = client.post("/api/search", json={"query": "alpha", "mode": "bm25"})

    assert response.status_code == 422


def test_search_rejects_non_positive_top_k(client: TestClient) -> None:
    response = client.post("/api/search", json={"query": "alpha", "top_k": 0})

    assert response.status_code == 422


def test_search_rejects_too_long_query(client: TestClient) -> None:
    response = client.post("/api/search", json={"query": "x" * 21})

    assert response.status_code == 400
    assert response.json() == {"detail": "Query is too long: maximum 20 characters"}


def test_search_rejects_too_large_top_k(client: TestClient) -> None:
    response = client.post("/api/search", json={"query": "alpha", "top_k": 11})

    assert response.status_code == 400
    assert response.json() == {"detail": "top_k must not exceed 10"}


def test_search_returns_503_on_backend_failure(settings: Settings) -> None:
    app = create_app(
        settings,
        AppServices(retriever=BrokenRetriever(), store=FakeStore()),
    )

    with TestClient(app) as client:
        response = client.post("/api/search", json={"query": "alpha"})

    assert response.status_code == 503
    assert response.json() == {"detail": "Search is temporarily unavailable"}
