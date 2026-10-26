from pathlib import Path

from docs_rag.ingestion.includes import resolve_includes


def test_resolves_code_include_into_fenced_block(tmp_path: Path) -> None:
    source = tmp_path / "docs"
    docs_src = source / "docs_src" / "dependencies"
    docs_src.mkdir(parents=True)
    (docs_src / "example.py").write_text(
        "from fastapi import Depends\n\nasync def dependency():\n    return 1\n",
        encoding="utf-8",
    )

    markdown = """\
# Example

{* ../../docs_src/dependencies/example.py hl[1] *}
"""

    resolved = resolve_includes(markdown, source)

    assert "```python" in resolved
    assert "from fastapi import Depends" in resolved
    assert "hl[1]" not in resolved


def test_resolves_raw_include_inside_fence_without_nested_fence(tmp_path: Path) -> None:
    source = tmp_path / "docs"
    docs_src = source / "docs_src" / "templates"
    docs_src.mkdir(parents=True)
    (docs_src / "item.html").write_text("<div>{{ item.id }}</div>", encoding="utf-8")

    markdown = """\
# Template

```jinja
{! ../../docs_src/templates/item.html !}
```
"""

    resolved = resolve_includes(markdown, source)

    assert resolved.count("```") == 2
    assert "<div>{{ item.id }}</div>" in resolved


def test_missing_include_is_kept(tmp_path: Path) -> None:
    source = tmp_path / "docs"
    source.mkdir()
    markdown = "{* ../../docs_src/missing.py *}\n"

    assert resolve_includes(markdown, source) == markdown


def test_no_docs_src_returns_original(tmp_path: Path) -> None:
    markdown = "# Docs\n\nText.\n"

    assert resolve_includes(markdown, tmp_path) == markdown
