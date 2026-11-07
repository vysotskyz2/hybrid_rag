from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest

from docs_rag.config import Settings
from docs_rag.generation.llm import (
    ChatMessage,
    FakeLLM,
    LLMError,
    OpenRouterLLM,
    build_llm,
)


def sse(*events: dict[str, Any] | str) -> bytes:
    lines = []
    for event in events:
        data = event if isinstance(event, str) else json.dumps(event)
        lines.append(f"data: {data}\n\n")
    return "".join(lines).encode()


async def collect(stream: AsyncIterator[str]) -> list[str]:
    return [chunk async for chunk in stream]


async def test_stream_chat_parses_openrouter_sse() -> None:
    captured: dict[str, Any] = {}
    body = sse(
        {"choices": [{"delta": {"content": "Hello"}}]},
        {"choices": [{"delta": {"content": " world"}}]},
        "[DONE]",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers.get("authorization")
        captured["payload"] = json.loads(request.read())
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content=body,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        llm = OpenRouterLLM(
            base_url="https://openrouter.ai/api/v1",
            api_key="test-key",
            model="deepseek/test",
            temperature=0.3,
            max_tokens=100,
            client=client,
        )
        chunks = await collect(llm.stream_chat([ChatMessage(role="user", content="Hi")]))

    assert chunks == ["Hello", " world"]
    assert captured["authorization"] == "Bearer test-key"
    payload = captured["payload"]
    assert payload["model"] == "deepseek/test"
    assert payload["stream"] is True
    assert payload["temperature"] == 0.3
    assert payload["max_tokens"] == 100
    assert payload["messages"] == [{"role": "user", "content": "Hi"}]


async def test_stream_chat_raises_on_http_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "rate limited"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        llm = OpenRouterLLM(
            base_url="https://openrouter.ai/api/v1",
            api_key="test-key",
            model="deepseek/test",
            client=client,
        )
        with pytest.raises(LLMError, match="HTTP 429"):
            await collect(llm.stream_chat([ChatMessage(role="user", content="Hi")]))


async def test_stream_chat_raises_on_malformed_data() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"data: not-json\n\n")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        llm = OpenRouterLLM(
            base_url="https://openrouter.ai/api/v1",
            api_key="test-key",
            model="deepseek/test",
            client=client,
        )
        with pytest.raises(LLMError, match="malformed"):
            await collect(llm.stream_chat([ChatMessage(role="user", content="Hi")]))


async def test_stream_chat_raises_on_provider_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=sse({"error": {"message": "bad key"}}))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        llm = OpenRouterLLM(
            base_url="https://openrouter.ai/api/v1",
            api_key="test-key",
            model="deepseek/test",
            client=client,
        )
        with pytest.raises(LLMError, match="bad key"):
            await collect(llm.stream_chat([ChatMessage(role="user", content="Hi")]))


async def test_llm_without_key_is_unavailable() -> None:
    async with httpx.AsyncClient() as client:
        llm = OpenRouterLLM(
            base_url="https://openrouter.ai/api/v1",
            api_key=None,
            model="deepseek/test",
            client=client,
        )
        assert llm.available is False
        with pytest.raises(LLMError, match="not configured"):
            await collect(llm.stream_chat([ChatMessage(role="user", content="Hi")]))


async def test_fake_llm_streams_and_records_messages() -> None:
    fake = FakeLLM(chunks=("a", "b"))
    messages = [ChatMessage(role="user", content="Hi")]

    assert await collect(fake.stream_chat(messages)) == ["a", "b"]
    assert fake.calls == [messages]

    await fake.aclose()
    assert fake.closed is True


async def test_fake_llm_can_fail_after_partial_answer() -> None:
    fake = FakeLLM(chunks=("partial",), error_after=1)

    with pytest.raises(LLMError, match="fake llm failure"):
        await collect(fake.stream_chat([ChatMessage(role="user", content="Hi")]))


async def test_build_llm_uses_fake_mode() -> None:
    llm = build_llm(Settings(_env_file=None, llm_mode="fake"))

    assert isinstance(llm, FakeLLM)

    await llm.aclose()


async def test_build_llm_uses_openrouter_key() -> None:
    llm = build_llm(Settings(_env_file=None, llm_api_key="secret"))

    assert isinstance(llm, OpenRouterLLM)
    assert llm.available is True

    await llm.aclose()
