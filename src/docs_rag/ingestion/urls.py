from pathlib import PurePosixPath


def doc_url(relative_path: str, base_url: str) -> str:
    path = PurePosixPath(relative_path)
    if path.suffix.lower() != ".md":
        raise ValueError(f"Expected a Markdown path, got: {relative_path}")

    parts = list(path.with_suffix("").parts)
    if parts and parts[-1] == "index":
        parts = parts[:-1]

    suffix = "/".join(parts)
    base = base_url.rstrip("/")
    return f"{base}/{suffix}/" if suffix else f"{base}/"


def section_for_path(relative_path: str) -> str:
    parts = PurePosixPath(relative_path).parts
    return parts[0] if len(parts) > 1 else "root"
