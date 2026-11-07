from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from docs_rag.api.deps import AppServices
from docs_rag.api.main import create_app
from docs_rag.config import Settings
from docs_rag.generation.llm import FakeLLM
from docs_rag.generation.prompt import NO_CONTEXT_ANSWER
from docs_rag.retrieval.models import SearchFilters
from tests.api.helpers import (
    BrokenSearchService,
    FakeSearchService,
    FakeStore,
    UnavailableLLM,
)


def parse_sse(text: str) -> list[tuple[str, dict[str, Any]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    for block in text.replace("\r\n", "\n").strip().split("\n\n"):
        if not block.strip():
            continue
        event = "message"
        data_lines: list[str] = []
        for line in block.splitlines():
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data_lines.append(line[5:].strip())
        if data_lines:
            events.append((event, json.loads("\n".join(data_lines))))
    return events


def test_ask_streams_sources_tokens_and_done(
    client: TestClient,
    fake_search: FakeSearchService,
    fake_llm: FakeLLM,
) -> None:
    response = client.post("/api/ask", json={"query": "How do I use Depends"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(response.text)
    assert [event for event, _ in events] == [
        "sources",
        "token",
        "token",
        "token",
        "done",
    ]

    sources = events[0][1]["sources"]
    assert [source["index"] for source in sources] == [1]
    assert sources[0]["chunk_id"] == "chunk-1"
    assert sources[0]["retrieval_score"] == 0.5
    assert sources[0]["text"] == "Dependency injection text"

    answer = "".join(data["text"] for event, data in events if event == "token")
    assert answer == "Fake answer [1]."

    done = events[-1][1]
    assert done["model"] == "fake"
    assert done["sources"] == 1
    assert done["reranked"] is True

    assert fake_search.calls == [
        ("How do I use Depends", "hybrid", 5, SearchFilters(), True),
    ]
    assert len(fake_llm.calls) == 1
    system, user = fake_llm.calls[0]
    assert system.role == "system"
    assert "Cite every" in system.content
    assert "How do I use Depends" in user.content
    assert "[1] Dependencies" in user.content
    assert "Dependency injection text" in user.content


def test_ask_passes_filters(client: TestClient, fake_search: FakeSearchService) -> None:
    response = client.post(
        "/api/ask",
        json={
            "query": "Depends",
            "section": "tutorial",
            "content_type": "prose",
            "language": "en",
            "version": "v1",
        },
    )

    assert response.status_code == 200
    assert fake_search.calls[0][3] == SearchFilters(
        section="tutorial",
        content_type="prose",
        language="en",
        version="v1",
    )


def test_ask_requires_llm(settings: Settings) -> None:
    app = create_app(
        settings,
        AppServices(
            search=FakeSearchService(),
            store=FakeStore(),
            llm=UnavailableLLM(),
        ),
    )

    with TestClient(app) as client:
        response = client.post("/api/ask", json={"query": "Depends"})

    assert response.status_code == 503
    assert "LLM is not configured" in response.json()["detail"]


def test_ask_without_sources_skips_llm(settings: Settings) -> None:
    llm = FakeLLM()
    app = create_app(
        settings,
        AppServices(
            search=FakeSearchService(results=[]),
            store=FakeStore(),
            llm=llm,
        ),
    )

    with TestClient(app) as client:
        response = client.post("/api/ask", json={"query": "unknown"})

    assert response.status_code == 200
    events = parse_sse(response.text)
    assert [event for event, _ in events] == ["sources", "token", "done"]
    assert events[0][1]["sources"] == []
    assert events[1][1]["text"] == NO_CONTEXT_ANSWER
    assert events[2][1]["sources"] == 0
    assert llm.calls == []


def test_ask_streams_error_after_partial_answer(settings: Settings) -> None:
    app = create_app(
        settings,
        AppServices(
            search=FakeSearchService(),
            store=FakeStore(),
            llm=FakeLLM(chunks=("partial",), error_after=1),
        ),
    )

    with TestClient(app) as client:
        response = client.post("/api/ask", json={"query": "Depends"})

    assert response.status_code == 200
    events = parse_sse(response.text)
    assert [event for event, _ in events] == ["sources", "token", "error"]
    assert events[1][1]["text"] == "partial"
    assert events[2][1]["code"] == "llm_error"


def test_ask_returns_503_on_retrieval_failure(settings: Settings) -> None:
    app = create_app(
        settings,
        AppServices(
            search=BrokenSearchService(),
            store=FakeStore(),
            llm=FakeLLM(),
        ),
    )

    with TestClient(app) as client:
        response = client.post("/api/ask", json={"query": "Depends"})

    assert response.status_code == 503
    assert response.json() == {"detail": "Search is temporarily unavailable"}


@pytest.mark.parametrize(
    ("payload", "status_code"),
    [
        ({"query": ""}, 422),
        ({"query": "   "}, 422),
        ({"query": "x" * 21}, 400),
        ({"query": "alpha", "mode": "bm25"}, 422),
        ({"query": "alpha", "top_k": 0}, 422),
        ({"query": "alpha", "top_k": 11}, 400),
    ],
)
def test_ask_validates_request(
    client: TestClient,
    payload: dict[str, object],
    status_code: int,
) -> None:
    response = client.post("/api/ask", json=payload)

    assert response.status_code == status_code
