import pytest

from docs_rag.ingestion.urls import doc_url, section_for_path


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("index.md", "https://example.com/"),
        ("tutorial/index.md", "https://example.com/tutorial/"),
        ("tutorial/body.md", "https://example.com/tutorial/body/"),
        (
            "tutorial/dependencies/index.md",
            "https://example.com/tutorial/dependencies/",
        ),
        (
            "reference/openapi/docs.md",
            "https://example.com/reference/openapi/docs/",
        ),
    ],
)
def test_doc_url(path: str, expected: str) -> None:
    assert doc_url(path, "https://example.com") == expected


def test_doc_url_rejects_non_markdown() -> None:
    with pytest.raises(ValueError):
        doc_url("tutorial/body.txt", "https://example.com")


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("index.md", "root"),
        ("tutorial/body.md", "tutorial"),
        ("advanced/security/http-basic-auth.md", "advanced"),
    ],
)
def test_section_for_path(path: str, expected: str) -> None:
    assert section_for_path(path) == expected
