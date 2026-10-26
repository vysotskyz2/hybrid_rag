from pathlib import PurePosixPath

from docs_rag.ingestion.config import FilteringConfig


def is_indexable(relative_path: str, filtering: FilteringConfig) -> bool:
    path = PurePosixPath(relative_path)
    normalized = path.as_posix()

    if path.suffix.lower() != ".md":
        return False
    if filtering.skip_underscore and path.name.startswith("_"):
        return False
    if normalized in filtering.excluded_paths:
        return False
    return not any(part in filtering.excluded_dirs for part in path.parts)
