from __future__ import annotations

from dataclasses import dataclass

from docs_rag.generation.llm import ChatMessage
from docs_rag.retrieval.models import SearchResult

SYSTEM_PROMPT = """You are DocsLens, a documentation assistant for FastAPI.

Rules:
- Answer only using the provided sources.
- If the sources do not contain the answer, say so explicitly.
- Do not use outside knowledge and do not invent API names, URLs, or examples.
- Cite every factual statement with source numbers in square brackets, for example [1].
- Answer in the same language as the user's question.
- Use Markdown and keep the answer concise.
"""

NO_CONTEXT_ANSWER = (
    "В документации не удалось найти подходящих источников. "  # noqa: RUF001
    "Уточните вопрос или попробуйте переформулировать его.\n\n"  # noqa: RUF001
    "No relevant documentation sources were found. "
    "Try rephrasing the question."
)


@dataclass(frozen=True, slots=True)
class PromptBundle:
    messages: tuple[ChatMessage, ...]
    sources: tuple[SearchResult, ...]


def select_sources(
    results: list[SearchResult],
    max_tokens: int,
) -> tuple[SearchResult, ...]:
    selected: list[SearchResult] = []
    used = 0
    for result in results:
        if selected and used + result.token_count > max_tokens:
            break
        selected.append(result)
        used += result.token_count
        if used >= max_tokens:
            break
    return tuple(selected)


def build_prompt(
    query: str,
    results: list[SearchResult],
    max_tokens: int,
) -> PromptBundle | None:
    sources = select_sources(results, max_tokens)
    if not sources:
        return None

    context = "\n\n".join(
        _format_source(index, source) for index, source in enumerate(sources, start=1)
    )
    messages = (
        ChatMessage(role="system", content=SYSTEM_PROMPT),
        ChatMessage(
            role="user",
            content=(
                f"Question:\n{query}\n\n"
                f"Sources:\n{context}\n\n"
                "Answer the question using only these sources."
            ),
        ),
    )
    return PromptBundle(messages=messages, sources=sources)


def _format_source(index: int, source: SearchResult) -> str:
    return (
        f"[{index}] {source.title}\n"
        f"Section: {source.heading_path}\n"
        f"URL: {source.url}\n"
        f"Text:\n{source.text}"
    )
