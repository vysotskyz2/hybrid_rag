from __future__ import annotations

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


def _format_option(value: str) -> str:
    return value if value else "все"


def render_results(data: dict[str, Any]) -> None:
    results = data.get("results", [])
    if not results:
        st.info("Ничего не найдено.")
        return

    st.caption(
        f"Режим: {data.get('mode')} · top-k: {data.get('top_k')} · результатов: {len(results)}"
    )
    for rank, item in enumerate(results, start=1):
        with st.container(border=True):
            title = item.get("title") or item.get("path") or "Без названия"
            st.markdown(f"**{rank}. {title}**")
            st.caption(
                f"{item.get('heading_path', '')} · раздел: {item.get('section', '')} · "
                f"тип: {item.get('content_type', '')} · "
                f"score: {float(item.get('score', 0)):.4f}"
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
        score = float(item.get("score", 0))
        st.markdown(f"**{rank}. {title}**")
        st.caption(f"score: {score:.4f}")
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
        "- фильтры по разделу и типу содержимого"
    )

st.title("DocsLens")
st.caption("Гибридный поиск по документации FastAPI: dense + BM25")

search_tab, compare_tab = st.tabs(["Поиск", "Сравнение"])

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
