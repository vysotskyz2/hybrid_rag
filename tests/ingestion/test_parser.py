from docs_rag.ingestion.parser import clean_heading_text, parse_markdown


def test_parse_markdown_tracks_heading_paths_and_code_fences() -> None:
    markdown = """\
# Title { #title }

Intro text.

## Section A { #section-a }

Text A.

```python
# this is not a heading
print("hello")
```

### Subsection { #subsection }

Text B.

## Section B { #section-b }

Text C.
"""

    parsed = parse_markdown(markdown)

    assert parsed.title == "Title"
    assert [section.title for section in parsed.sections] == [
        "Title",
        "Section A",
        "Subsection",
        "Section B",
    ]

    sections = {section.title: section for section in parsed.sections}
    section_a = sections["Section A"]
    subsection = sections["Subsection"]
    section_b = sections["Section B"]

    assert section_a.heading_path == ("Title", "Section A")
    assert subsection.heading_path == ("Title", "Section A", "Subsection")
    assert section_b.heading_path == ("Title", "Section B")
    assert "# this is not a heading" in section_a.content
    assert "## Section B" not in section_a.content


def test_parse_markdown_keeps_intro_before_first_heading() -> None:
    parsed = parse_markdown("Intro line.\n\n# Title { #title }\n\nBody.")

    assert parsed.title == "Title"
    assert parsed.sections[0].level == 0
    assert parsed.sections[0].heading_path == ()
    assert parsed.sections[0].content == "Intro line."


def test_parse_markdown_skips_frontmatter() -> None:
    parsed = parse_markdown("---\nrender_macros: false\n---\n\n# Title { #title }\n\nBody.")

    assert parsed.title == "Title"
    assert parsed.sections[0].title == "Title"
    assert "render_macros" not in parsed.sections[0].content


def test_parse_markdown_removes_html_comments() -> None:
    parsed = parse_markdown(
        "# Title { #title }\n\n## Section { #section }\n\n<!-- sponsors -->\n\nText."
    )

    assert parsed.sections[0].content == "Text."


def test_clean_heading_text_removes_anchor_and_closing_hashes() -> None:
    assert clean_heading_text("Dependencies { #dependencies }") == "Dependencies"
    assert clean_heading_text("`FastAPI` class { #fastapi-class }") == "FastAPI class"
    assert clean_heading_text("Title ##") == "Title"
