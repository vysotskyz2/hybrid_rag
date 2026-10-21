from fastapi.testclient import TestClient

from docs_rag.api.main import create_app
from docs_rag.config import Settings


def test_health() -> None:
    app = create_app(Settings(_env_file=None))

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root() -> None:
    app = create_app(Settings(_env_file=None))

    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert response.json()["name"] == "DocsLens"
    assert response.json()["version"] == "0.1.0"
