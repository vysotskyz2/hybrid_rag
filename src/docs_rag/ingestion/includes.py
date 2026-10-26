import re
from pathlib import Path, PurePosixPath

_INCLUDE_RE = re.compile(
    r"^\{\*\s*(?P<code_path>[^\s*]+)(?P<options>[^*]*)\*\}$"
    r"|^\{!\s*(?P<raw_path>.+?)\s*!\}$"
)
_FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})(.*)$")

_LANGUAGE_BY_SUFFIX = {
    ".py": "python",
    ".html": "html",
    ".jinja": "jinja",
    ".jinja2": "jinja",
    ".js": "javascript",
    ".json": "json",
    ".sql": "sql",
    ".sh": "bash",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".toml": "toml",
    ".txt": "text",
    ".md": "markdown",
}


def resolve_includes(
    markdown: str,
    source_dir: Path,
    docs_src_path: str = "docs_src",
    enabled: bool = True,
) -> str:
    if not enabled:
        return markdown

    docs_src = source_dir / docs_src_path
    if not docs_src.exists():
        return markdown

    output: list[str] = []
    fence_char: str | None = None
    fence_len = 0

    for line in markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if fence_char is not None:
            match = _INCLUDE_RE.match(line.strip())
            if match:
                included = _read_include(match, docs_src)
                if included is not None:
                    output.extend(included[1].splitlines())
                    continue
            output.append(line)
            close_match = _FENCE_RE.match(line)
            if (
                close_match
                and close_match.group(1)[0] == fence_char
                and len(close_match.group(1)) >= fence_len
            ):
                fence_char = None
                fence_len = 0
            continue

        open_match = _FENCE_RE.match(line)
        if open_match:
            fence_char = open_match.group(1)[0]
            fence_len = len(open_match.group(1))
            output.append(line)
            continue

        match = _INCLUDE_RE.match(line.strip())
        if match:
            included = _read_include(match, docs_src)
            if included is not None:
                language, content = included
                output.append(f"```{language}")
                output.extend(content.splitlines())
                output.append("```")
                continue

        output.append(line)

    return "\n".join(output)


def _read_include(match: re.Match[str], docs_src: Path) -> tuple[str, str] | None:
    include_path = match.group("code_path") or match.group("raw_path")
    if not include_path:
        return None

    normalized = include_path.replace("\\", "/")
    marker = "docs_src/"
    marker_index = normalized.find(marker)
    if marker_index < 0:
        return None

    relative = PurePosixPath(normalized[marker_index + len(marker) :])
    if relative.is_absolute() or ".." in relative.parts:
        return None

    file_path = docs_src.joinpath(*relative.parts)
    if not file_path.is_file():
        return None

    content = file_path.read_text(encoding="utf-8").rstrip()
    language = _LANGUAGE_BY_SUFFIX.get(file_path.suffix.lower(), file_path.suffix.lstrip("."))
    return language, content
