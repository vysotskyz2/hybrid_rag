from docs_rag.generation.prompt import NO_CONTEXT_ANSWER, build_prompt, select_sources
from tests.api.helpers import make_search_result


def test_build_prompt_numbers_sources() -> None:
    results = [
        make_search_result(chunk_id="first", title="First", text="First text", token_count=10),
        make_search_result(chunk_id="second", title="Second", text="Second text", token_count=10),
    ]

    bundle = build_prompt("How do I use Depends?", results, max_tokens=100)

    assert bundle is not None
    assert [source.chunk_id for source in bundle.sources] == ["first", "second"]
    system, user = bundle.messages
    assert "provided sources" in system.content
    assert "Cite every" in system.content
    assert "How do I use Depends?" in user.content
    assert "[1] First" in user.content
    assert "[2] Second" in user.content
    assert "First text" in user.content
    assert "Second text" in user.content


def test_build_prompt_respects_token_budget() -> None:
    results = [
        make_search_result(chunk_id="first", text="First text", token_count=10),
        make_search_result(chunk_id="second", text="Second text", token_count=20),
        make_search_result(chunk_id="third", text="Third text", token_count=30),
    ]

    bundle = build_prompt("question", results, max_tokens=35)

    assert bundle is not None
    assert [source.chunk_id for source in bundle.sources] == ["first", "second"]
    user = bundle.messages[1]
    assert "[2]" in user.content
    assert "[3]" not in user.content


def test_build_prompt_returns_none_without_sources() -> None:
    assert build_prompt("question", [], max_tokens=100) is None


def test_select_sources_keeps_first_source_over_budget() -> None:
    result = make_search_result(token_count=100)

    assert select_sources([result], max_tokens=10) == (result,)


def test_no_context_answer_is_bilingual() -> None:
    assert "документации" in NO_CONTEXT_ANSWER
    assert "No relevant" in NO_CONTEXT_ANSWER
