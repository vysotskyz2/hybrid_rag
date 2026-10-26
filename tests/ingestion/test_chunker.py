from pathlib import Path

from docs_rag.ingestion.chunker import chunk_document
from docs_rag.ingestion.config import ChunkingConfig
from docs_rag.ingestion.models import DocFile
from docs_rag.ingestion.tokens import RegexTokenCounter
from docs_rag.ingestion.urls import doc_url, section_for_path
from tests.ingestion.helpers import make_config


def make_doc(text: str, path: str = "tutorial/demo.md") -> DocFile:
    return DocFile(
        relative_path=path,
        text=text,
        url=doc_url(path, "https://example.com"),
        title=Path(path).stem,
        section=section_for_path(path),
    )


def test_chunk_document_builds_metadata_and_heading_context() -> None:
    markdown = """\
# Demo { #demo }

## Install { #install }

Install FastAPI with pip. FastAPI is a modern, fast web framework for building APIs
with Python type hints. It provides automatic OpenAPI documentation and validation.

```python
from fastapi import FastAPI
```
"""
    config = make_config()
    chunks = chunk_document(make_doc(markdown), config, RegexTokenCounter())

    assert len(chunks) == 1
    chunk = chunks[0]

    assert chunk.title == "Demo"
    assert chunk.heading_path == "Demo > Install"
    assert chunk.text.startswith("Demo > Install\n\n")
    assert chunk.url == "https://example.com/tutorial/demo/"
    assert chunk.section == "tutorial"
    assert chunk.language == "en"
    assert chunk.version == config.corpus.ref
    assert chunk.doc_id == "tutorial/demo.md"
    assert chunk.chunk_index == 0
    assert chunk.content_type == "mixed"
    assert chunk.chunk_id
    assert chunk.content_hash
    assert chunk.token_count > 0


def test_long_section_is_split_with_overlap() -> None:
    words = " ".join(f"word{index}" for index in range(220))
    markdown = f"# Demo {{ #demo }}\n\n## Long {{ #long }}\n\n{words}\n"
    config = make_config(chunking=ChunkingConfig(max_tokens=50, overlap_tokens=10))
    chunks = chunk_document(make_doc(markdown), config, RegexTokenCounter())

    assert len(chunks) > 1
    assert all(chunk.token_count <= config.chunking.max_tokens for chunk in chunks)
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))

    first_tail = chunks[0].text.split()[-5:]
    assert " ".join(first_tail) in chunks[1].text


def test_oversized_code_block_is_split_without_broken_fences() -> None:
    code_lines = "\n".join(f"value_{index} = {index}" for index in range(120))
    markdown = f"# Demo {{ #demo }}\n\n## Code {{ #code }}\n\n```python\n{code_lines}\n```\n"
    config = make_config(chunking=ChunkingConfig(max_tokens=60, overlap_tokens=5))
    chunks = chunk_document(make_doc(markdown), config, RegexTokenCounter())

    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.token_count <= config.chunking.max_tokens
        assert chunk.text.count("```") == 2
        assert chunk.text.split("```python", 1)[1].rsplit("```", 1)[0].strip()


def test_chunk_ids_are_deterministic() -> None:
    markdown = "# Demo { #demo }\n\n## Section { #section }\n\nText.\n"
    config = make_config()

    first = chunk_document(make_doc(markdown), config, RegexTokenCounter())
    second = chunk_document(make_doc(markdown), config, RegexTokenCounter())

    assert [chunk.chunk_id for chunk in first] == [chunk.chunk_id for chunk in second]
    assert [chunk.content_hash for chunk in first] == [chunk.content_hash for chunk in second]


def test_html_tags_are_stripped_outside_code_blocks() -> None:
    markdown = """\
# Demo { #demo }

## Section { #section }

<dfn title="definition">Dependency Injection</dfn> is useful.

```html
<div class="example">keep me</div>
```
"""
    config = make_config()
    chunks = chunk_document(make_doc(markdown), config, RegexTokenCounter())

    assert "<dfn" not in chunks[0].text
    assert "Dependency Injection" in chunks[0].text
    assert '<div class="example">' in chunks[0].text


def test_sponsor_sections_are_skipped() -> None:
    markdown = """\
# Demo { #demo }

## Sponsors { #sponsors }

<div>Sponsor boilerplate</div>

## Install { #install }

Useful content.
"""
    config = make_config()
    chunks = chunk_document(make_doc(markdown), config, RegexTokenCounter())

    assert len(chunks) == 1
    assert chunks[0].heading_path == "Demo > Install"
    assert "Sponsor boilerplate" not in chunks[0].text


def test_content_type_is_code_for_code_only_section() -> None:
    markdown = "# Demo { #demo }\n\n## Code { #code }\n\n```python\nprint('hi')\n```\n"
    config = make_config()

    chunks = chunk_document(make_doc(markdown), config, RegexTokenCounter())

    assert chunks[0].content_type == "code"
