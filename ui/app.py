from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import httpx
import streamlit as st

from docs_rag.config import get_settings

st.set_page_config(
    page_title="DocsLens",
    layout="wide",
)

SETTINGS = get_settings()
API_URL = SETTINGS.ui_api_url.rstrip("/")
MODES = ("hybrid", "dense", "sparse")
COMPARE_MODES = ("dense", "sparse", "hybrid")
CONTENT_TYPES = ("", "prose", "code", "mixed")
SECTIONS = ("", "tutorial", "advanced", "how-to", "reference", "deployment", "root")
MAX_TOP_K = SETTINGS.search_max_top_k
DEFAULT_TOP_K = min(SETTINGS.retrieval_top_k, MAX_TOP_K)

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []


class ApiError(Exception):
    pass


def _error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return f"HTTP {response.status_code}: {response.text[:300]}"

    if isinstance(payload, dict):
        detail = payload.get("detail")
        reason = payload.get("reason")
        if isinstance(detail, list):
            messages = [
                str(item.get("msg", item)) if isinstance(item, dict) else str(item)
                for item in detail
            ]
            detail = "; ".join(messages)
        if detail and reason:
            return f"{detail}. {reason}"
        if detail:
            return str(detail)

    return f"HTTP {response.status_code}"


@st.cache_resource(show_spinner=False)
def get_client(api_url: str) -> httpx.Client:
    return httpx.Client(base_url=api_url, timeout=60.0)


@st.cache_data(ttl=10, show_spinner=False)
def fetch_ready(api_url: str) -> dict[str, Any]:
    try:
        response = httpx.get(f"{api_url}/ready", timeout=5.0)
    except httpx.HTTPError as exc:
        return {"ready": False, "detail": f"API недоступен: {exc}"}

    if response.status_code == 200:
        payload = response.json()
        return {
            "ready": True,
            "points": payload.get("points"),
            "detail": "Индекс готов",
        }
    return {"ready": False, "detail": _error_detail(response)}


def api_request(
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    try:
        response = get_client(API_URL).request(method, path, json=payload)
    except httpx.HTTPError as exc:
        st.error(f"API недоступен: {exc}")
        return None

    if response.status_code >= 400:
        st.error(f"Ошибка API: {_error_detail(response)}")
        return None
    return response.json()


def api_search(
    query: str,
    mode: str,
    top_k: int,
    section: str,
    content_type: str,
) -> dict[str, Any] | None:
    payload: dict[str, Any] = {"query": query, "mode": mode, "top_k": top_k}
    if section:
        payload["section"] = section
    if content_type:
        payload["content_type"] = content_type
    return api_request("POST", "/api/search", payload)


def api_ask_events(payload: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    try:
        with get_client(API_URL).stream(
            "POST",
            "/api/ask",
            json=payload,
            timeout=180.0,
        ) as response:
            if response.status_code >= 400:
                response.read()
                raise ApiError(_error_detail(response))

            event = "message"
            data_lines: list[str] = []
            for line in response.iter_lines():
                if not line:
                    if data_lines:
                        try:
                            data = json.loads("\n".join(data_lines))
                        except json.JSONDecodeError as exc:
                            raise ApiError("API вернул некорректный SSE-ответ") from exc
                        yield event, data
                    event = "message"
                    data_lines = []
                    continue
                if line.startswith(":"):
                    continue
                if line.startswith("event:"):
                    event = line[6:].strip()
                elif line.startswith("data:"):
                    data_lines.append(line[5:].lstrip())
    except httpx.HTTPError as exc:
        raise ApiError(f"API недоступен: {exc}") from exc


def _format_option(value: str) -> str:
    return value if value else "все"


def _score_text(item: dict[str, Any]) -> str:
    text = f"score: {float(item.get('score', 0)):.4f}"
    if item.get("retrieval_score") is not None:
        text += f" (retrieval: {float(item['retrieval_score']):.4f})"
    return text


def render_sources(sources: list[dict[str, Any]]) -> None:
    if not sources:
        return

    st.markdown("**Источники**")
    for source in sources:
        title = source.get("title") or source.get("path") or "Без названия"
        with st.container(border=True):
            st.markdown(f"**[{source.get('index')}] {title}**")
            st.caption(
                f"{source.get('heading_path', '')} · раздел: {source.get('section', '')} · "
                f"{_score_text(source)}"
            )
            url = source.get("url")
            if url:
                st.markdown(f"[Открыть документацию]({url})")
            with st.expander("Текст источника"):
                st.markdown(source.get("text", ""))


def render_chat_message(message: dict[str, Any]) -> None:
    with st.chat_message(message.get("role", "assistant")):
        content = message.get("content", "")
        if content:
            st.markdown(content)
        if message.get("error"):
            st.error(message["error"])
        if message.get("sources"):
            render_sources(message["sources"])


def render_results(data: dict[str, Any]) -> None:
    results = data.get("results", [])
    if not results:
        st.info("Ничего не найдено.")
        return

    st.caption(
        f"Режим: {data.get('mode')} · top-k: {data.get('top_k')} · "
        f"результатов: {len(results)} · reranked: {data.get('reranked', False)}"
    )
    for rank, item in enumerate(results, start=1):
        with st.container(border=True):
            title = item.get("title") or item.get("path") or "Без названия"
            st.markdown(f"**{rank}. {title}**")
            st.caption(
                f"{item.get('heading_path', '')} · раздел: {item.get('section', '')} · "
                f"тип: {item.get('content_type', '')} · {_score_text(item)}"
            )
            url = item.get("url")
            if url:
                st.markdown(f"[Открыть документацию]({url})")
            st.caption(
                f"`{item.get('path', '')}` · язык: {item.get('language', '')} · "
                f"версия: {item.get('version', '')}"
            )
            with st.expander("Текст чанка"):
                st.markdown(item.get("text", ""))


def render_compact_results(data: dict[str, Any]) -> None:
    results = data.get("results", [])
    if not results:
        st.info("Ничего не найдено.")
        return

    for rank, item in enumerate(results, start=1):
        title = item.get("title") or item.get("path") or "Без названия"
        st.markdown(f"**{rank}. {title}**")
        st.caption(_score_text(item))
        st.caption(
            f"{item.get('heading_path', '')} · {item.get('section', '')} · "
            f"{item.get('content_type', '')}"
        )
        url = item.get("url")
        if url:
            st.markdown(f"[Открыть]({url})")
        st.divider()


with st.sidebar:
    st.header("Состояние API")
    ready_state = fetch_ready(API_URL)
    if ready_state["ready"]:
        st.success(f"Готово · {ready_state['points']} points")
    else:
        st.error(ready_state["detail"])
    st.caption(f"API: {API_URL}")
    if st.button("Проверить снова"):
        fetch_ready.clear()
        st.rerun()
    st.divider()
    st.markdown(
        "**Возможности**\n\n"
        "- поиск: dense / sparse / hybrid\n"
        "- сравнение режимов\n"
        "- фильтры по разделу и типу содержимого\n"
        "- ответы с цитатами в чате"  # noqa: RUF001
    )

st.title("DocsLens")
st.caption("Гибридный RAG по документации FastAPI: поиск, сравнение и ответы")

search_tab, compare_tab, chat_tab = st.tabs(["Поиск", "Сравнение", "Чат"])

with search_tab:
    with st.form("search-form"):
        query = st.text_input(
            "Запрос",
            placeholder="Например: как работает внедрение зависимостей?",
        )
        left, middle, right = st.columns(3)
        mode = left.selectbox("Режим поиска", MODES)
        top_k = middle.slider("top-k", 1, MAX_TOP_K, DEFAULT_TOP_K)
        content_type = right.selectbox(
            "Тип содержимого",
            CONTENT_TYPES,
            format_func=_format_option,
        )
        section = st.selectbox("Раздел", SECTIONS, format_func=_format_option)
        submitted = st.form_submit_button("Найти", type="primary")

    if submitted:
        if not query.strip():
            st.warning("Введите запрос.")
        else:
            with st.spinner("Ищу по индексу..."):
                search_data = api_search(query, mode, top_k, section, content_type)
            if search_data is not None:
                render_results(search_data)

with compare_tab:
    with st.form("compare-form"):
        compare_query = st.text_input(
            "Запрос для сравнения",
            placeholder="Например: How do I use Depends?",
        )
        left, right = st.columns(2)
        compare_top_k = left.slider("top-k", 1, MAX_TOP_K, DEFAULT_TOP_K, key="compare-top-k")
        compare_content_type = right.selectbox(
            "Тип содержимого",
            CONTENT_TYPES,
            format_func=_format_option,
            key="compare-content-type",
        )
        compare_section = st.selectbox(
            "Раздел",
            SECTIONS,
            format_func=_format_option,
            key="compare-section",
        )
        compare_submitted = st.form_submit_button("Сравнить режимы", type="primary")

    if compare_submitted:
        if not compare_query.strip():
            st.warning("Введите запрос.")
        else:
            columns = st.columns(3)
            for column, mode_name in zip(columns, COMPARE_MODES, strict=True):
                with column:
                    st.subheader(mode_name)
                    with st.spinner(f"Режим {mode_name}..."):
                        mode_data = api_search(
                            compare_query,
                            mode_name,
                            compare_top_k,
                            compare_section,
                            compare_content_type,
                        )
                    if mode_data is not None:
                        render_compact_results(mode_data)

with chat_tab:
    st.caption(
        f"Каждый вопрос обрабатывается независимо. LLM: {SETTINGS.llm_mode} / {SETTINGS.llm_model}."
    )
    if st.button("Очистить диалог", key="clear-chat"):
        st.session_state.chat_messages = []
        st.rerun()

    for message in st.session_state.chat_messages:
        render_chat_message(message)

    left, middle, right = st.columns(3)
    chat_mode = left.selectbox("Режим поиска", MODES, key="chat-mode")
    chat_top_k = middle.slider("top-k", 1, MAX_TOP_K, DEFAULT_TOP_K, key="chat-top-k")
    chat_content_type = right.selectbox(
        "Тип содержимого",
        CONTENT_TYPES,
        format_func=_format_option,
        key="chat-content-type",
    )
    chat_section = st.selectbox(
        "Раздел",
        SECTIONS,
        format_func=_format_option,
        key="chat-section",
    )

    prompt = st.chat_input("Спросите по документации...")
    if prompt:
        prompt = prompt.strip()
        if not prompt:
            st.warning("Введите вопрос.")
        else:
            st.session_state.chat_messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            payload: dict[str, Any] = {
                "query": prompt,
                "mode": chat_mode,
                "top_k": chat_top_k,
            }
            if chat_section:
                payload["section"] = chat_section
            if chat_content_type:
                payload["content_type"] = chat_content_type

            sources: list[dict[str, Any]] = []
            answer = ""
            error: str | None = None
            with st.chat_message("assistant"):
                placeholder = st.empty()
                try:
                    with st.spinner("Думаю..."):
                        for event, data in api_ask_events(payload):
                            if event == "sources":
                                sources = list(data.get("sources", []))
                            elif event == "token":
                                answer += str(data.get("text", ""))
                                placeholder.markdown(answer)
                            elif event == "error":
                                error = str(data.get("detail", "Ошибка генерации"))
                except ApiError as exc:
                    error = str(exc)
                if error:
                    st.error(error)
                if sources:
                    render_sources(sources)

            st.session_state.chat_messages.append(
                {
                    "role": "assistant",
                    "content": answer,
                    "sources": sources,
                    "error": error,
                }
            )
