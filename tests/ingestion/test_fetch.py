import io
import tarfile
from pathlib import Path

from docs_rag.ingestion.fetch import extract_docs


def add_member(tar: tarfile.TarFile, name: str, data: bytes) -> None:
    info = tarfile.TarInfo(name=name)
    info.size = len(data)
    tar.addfile(info, io.BytesIO(data))


def test_extract_docs_only_takes_markdown_from_target_prefix(tmp_path: Path) -> None:
    archive = tmp_path / "docs.tar.gz"

    with tarfile.open(archive, mode="w:gz") as tar:
        add_member(tar, "fastapi-abc/docs/en/docs/index.md", b"# Index")
        add_member(tar, "fastapi-abc/docs/en/docs/tutorial/body.md", b"# Body")
        add_member(tar, "fastapi-abc/docs/en/docs/notes.txt", b"ignored")
        add_member(tar, "fastapi-abc/docs/en/docs/../evil.md", b"# Evil")
        add_member(tar, "other-repo/docs/en/docs/skip.md", b"# Skip")

    dest = tmp_path / "extracted"
    extracted = extract_docs(
        archive,
        dest,
        prefix="docs/en/docs",
        archive_prefix="fastapi-abc",
    )

    relative = {path.relative_to(dest).as_posix() for path in extracted}
    assert relative == {"index.md", "tutorial/body.md"}
    assert (dest / "index.md").read_text(encoding="utf-8") == "# Index"
    assert not (dest / "evil.md").exists()
