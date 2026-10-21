from pathlib import PurePosixPath

EXCLUDED_PATHS = frozenset(
    {
        "_llm-test.md",
        "about/index.md",
        "contributing.md",
        "external-links.md",
        "fastapi-people.md",
        "help-fastapi.md",
        "learn/index.md",
        "management.md",
        "newsletter.md",
        "release-notes.md",
        "resources/index.md",
        "translation-banner.md",
        "translations.md",
    }
)

EXCLUDED_DIRS = frozenset({"img", "css", "js"})


def is_indexable(relative_path: str) -> bool:
    path = PurePosixPath(relative_path)
    normalized = path.as_posix()

    if path.suffix.lower() != ".md":
        return False
    if path.name.startswith("_"):
        return False
    if normalized in EXCLUDED_PATHS:
        return False
    return not any(part in EXCLUDED_DIRS for part in path.parts)
