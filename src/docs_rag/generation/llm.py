from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

import httpx

from docs_rag.config import Settings

Role = Literal["system", "user", "assistant"]


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: Role
    content: str


class LLMError(Exception):
    pass


class LLMClient(Protocol):
    @property
    def available(self) -> bool: ...

    @property
    def model(self) -> str: ...

    def stream_chat(self, messages: Sequence[ChatMessage]) -> AsyncIterator[str]: ...

    async def aclose(self) -> None: ...


class OpenRouterLLM:
    def __init__(
        self,
        base_url: str,
        api_key: str | None,
        model: str,
        temperature: float = 0.2,
        max_tokens: int = 800,
        timeout: int = 120,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=10.0),
        )
        self._owns_client = client is None

    @property
    def available(self) -> bool:
        return bool(self._api_key)

    @property
    def model(self) -> str:
        return self._model

    async def stream_chat(self, messages: Sequence[ChatMessage]) -> AsyncIterator[str]:
        if not self._api_key:
            raise LLMError("LLM is not configured")

        payload = {
            "model": self._model,
            "messages": [
                {"role": message.role, "content": message.content} for message in messages
            ],
            "stream": True,
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "X-Title": "DocsLens",
        }

        try:
            async with self._client.stream(
                "POST",
                f"{self._base_url}/chat/completions",
                json=payload,
                headers=headers,
            ) as response:
                if response.status_code >= 400:
                    body = (await response.aread()).decode("utf-8", errors="replace")
                    raise LLMError(f"OpenRouter HTTP {response.status_code}: {body[:500]}")

                async for line in response.aiter_lines():
                    data = _data_line(line)
                    if data is None:
                        continue
                    if data == "[DONE]":
                        return
                    try:
                        event = json.loads(data)
                    except json.JSONDecodeError as exc:
                        raise LLMError("OpenRouter returned malformed stream data") from exc
                    if "error" in event:
                        raise LLMError(f"OpenRouter error: {_error_message(event['error'])}")
                    choices = event.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    content = delta.get("content")
                    if isinstance(content, str) and content:
                        yield content
        except httpx.HTTPError as exc:
            raise LLMError(f"OpenRouter request failed: {exc}") from exc

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()


class FakeLLM:
    def __init__(
        self,
        chunks: tuple[str, ...] = ("Fake ", "answer ", "[1]."),
        error_after: int | None = None,
    ) -> None:
        self.calls: list[list[ChatMessage]] = []
        self.closed = False
        self._chunks = chunks
        self._error_after = error_after

    @property
    def available(self) -> bool:
        return True

    @property
    def model(self) -> str:
        return "fake"

    async def stream_chat(self, messages: Sequence[ChatMessage]) -> AsyncIterator[str]:
        self.calls.append(list(messages))
        for index, chunk in enumerate(self._chunks):
            if self._error_after is not None and index >= self._error_after:
                raise LLMError("fake llm failure")
            yield chunk
        if self._error_after is not None and self._error_after >= len(self._chunks):
            raise LLMError("fake llm failure")

    async def aclose(self) -> None:
        self.closed = True


def _data_line(line: str) -> str | None:
    stripped = line.strip()
    if not stripped or stripped.startswith(":") or not stripped.startswith("data:"):
        return None
    return stripped[5:].strip()


def _error_message(error: object) -> str:
    if isinstance(error, dict):
        message = error.get("message")
        if message is not None:
            return str(message)
    return str(error)


def build_llm(settings: Settings) -> LLMClient:
    if settings.llm_mode == "fake":
        return FakeLLM()
    api_key = settings.llm_api_key.get_secret_value() if settings.llm_api_key else None
    return OpenRouterLLM(
        base_url=settings.llm_base_url,
        api_key=api_key,
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        timeout=settings.llm_timeout,
    )
