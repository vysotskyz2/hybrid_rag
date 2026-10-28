import uuid

from fastapi.testclient import TestClient

ALLOWED_ORIGIN = "http://localhost:8501"


def test_cors_allows_configured_origin(client: TestClient) -> None:
    response = client.get("/health", headers={"Origin": ALLOWED_ORIGIN})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN


def test_cors_rejects_unknown_origin(client: TestClient) -> None:
    response = client.get("/health", headers={"Origin": "https://evil.example"})

    assert "access-control-allow-origin" not in response.headers


def test_cors_preflight(client: TestClient) -> None:
    response = client.options(
        "/api/search",
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN


def test_request_id_is_echoed(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "test-request"})

    assert response.headers["x-request-id"] == "test-request"


def test_request_id_is_generated(client: TestClient) -> None:
    response = client.get("/health")

    request_id = response.headers["x-request-id"]
    assert uuid.UUID(request_id)
    assert len(request_id) == 32
