import pytest

from docs_rag.ingestion.filters import is_indexable


@pytest.mark.parametrize(
    "path",
    [
        "release-notes.md",
        "translation-banner.md",
        "contributing.md",
        "about/index.md",
        "learn/index.md",
        "resources/index.md",
        "_llm-test.md",
        "img/diagram.md",
    ],
)
def test_excluded_paths(path: str) -> None:
    assert not is_indexable(path)


@pytest.mark.parametrize(
    "path",
    [
        "index.md",
        "tutorial/index.md",
        "tutorial/body.md",
        "advanced/security/oauth2-scopes.md",
        "reference/fastapi.md",
        "how-to/graphql.md",
        "deployment/docker.md",
    ],
)
def test_indexable_paths(path: str) -> None:
    assert is_indexable(path)


def test_non_markdown_is_not_indexable() -> None:
    assert not is_indexable("img/logo.png")
