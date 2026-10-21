import re

from docs_rag.ingestion.models import ParsedDocument, Section

_HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*$")
_FENCE_OPEN_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})(.*)$")
_FENCE_CLOSE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})\s*$")
_ANCHOR_RE = re.compile(r"\s*\{\s*#[^}]+\}\s*$")
_CLOSING_HASHES_RE = re.compile(r"\s+#+\s*$")
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def _strip_frontmatter(lines: list[str]) -> list[str]:
    if not lines or lines[0].strip() != "---":
        return lines

    for index in range(1, len(lines)):
        if lines[index].strip() in {"---", "..."}:
            return lines[index + 1 :]
    return lines


def clean_heading_text(text: str) -> str:
    cleaned = _ANCHOR_RE.sub("", text).strip()
    cleaned = _CLOSING_HASHES_RE.sub("", cleaned).strip()
    return cleaned.replace("`", "").strip()


def parse_markdown(markdown: str) -> ParsedDocument:
    lines = markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    lines = _strip_frontmatter(lines)
    sections: list[Section] = []
    stack: list[tuple[int, str]] = []
    current_level = 0
    current_title = ""
    current_path: tuple[str, ...] = ()
    current_lines: list[str] = []
    title: str | None = None
    fence_char: str | None = None
    fence_len = 0

    def flush() -> None:
        nonlocal current_lines
        content = _HTML_COMMENT_RE.sub("", "\n".join(current_lines)).strip()
        if content:
            sections.append(
                Section(
                    level=current_level,
                    title=current_title,
                    heading_path=current_path,
                    content=content,
                )
            )
        current_lines = []

    for line in lines:
        if fence_char is not None:
            current_lines.append(line)
            close_match = _FENCE_CLOSE_RE.match(line)
            if (
                close_match
                and close_match.group(1)[0] == fence_char
                and len(close_match.group(1)) >= fence_len
            ):
                fence_char = None
                fence_len = 0
            continue

        open_match = _FENCE_OPEN_RE.match(line)
        if open_match:
            fence_char = open_match.group(1)[0]
            fence_len = len(open_match.group(1))
            current_lines.append(line)
            continue

        heading_match = _HEADING_RE.match(line)
        if heading_match:
            flush()
            level = len(heading_match.group(1))
            heading_text = clean_heading_text(heading_match.group(2))
            if level == 1 and title is None:
                title = heading_text
            stack = [
                (stack_level, stack_title)
                for stack_level, stack_title in stack
                if stack_level < level
            ]
            stack.append((level, heading_text))
            current_level = level
            current_title = heading_text
            current_path = tuple(stack_title for _, stack_title in stack)
            continue

        current_lines.append(line)

    flush()
    return ParsedDocument(title=title, sections=tuple(sections))
