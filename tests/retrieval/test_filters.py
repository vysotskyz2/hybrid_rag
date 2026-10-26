from docs_rag.retrieval.filters import build_qdrant_filter
from docs_rag.retrieval.models import SearchFilters


def test_empty_filters_return_none() -> None:
    assert build_qdrant_filter(None) is None
    assert build_qdrant_filter(SearchFilters()) is None


def test_filters_are_converted_to_qdrant_conditions() -> None:
    result = build_qdrant_filter(
        SearchFilters(
            section="tutorial",
            content_type="prose",
            language="en",
            version="v1",
            path="tutorial/body.md",
        )
    )

    assert result is not None
    assert result.must is not None
    conditions = {
        condition.key: condition.match.value  # type: ignore[union-attr]
        for condition in result.must
    }
    assert conditions == {
        "section": "tutorial",
        "content_type": "prose",
        "language": "en",
        "version": "v1",
        "path": "tutorial/body.md",
    }


def test_only_present_filters_are_used() -> None:
    result = build_qdrant_filter(SearchFilters(section="tutorial"))

    assert result is not None
    assert result.must is not None
    assert len(result.must) == 1
