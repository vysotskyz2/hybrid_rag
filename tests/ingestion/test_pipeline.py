import json
from pathlib import Path

from docs_rag.ingestion.pipeline import build_corpus
from tests.ingestion.helpers import make_config


def test_build_corpus_writes_chunks_and_stats(tmp_path: Path) -> None:
    source = tmp_path / "source"
    (source / "tutorial").mkdir(parents=True)
    (source / "index.md").write_text(
        "# Home { #home }\n\nWelcome to the docs.\n",
        encoding="utf-8",
    )
    (source / "docs_src").mkdir()
    (source / "docs_src" / "example.py").write_text(
        "from fastapi import FastAPI\n",
        encoding="utf-8",
    )
    (source / "tutorial" / "body.md").write_text(
        "# Body { #body }\n\n## Example { #example }\n\n{* ../../docs_src/example.py hl[1] *}\n",
        encoding="utf-8",
    )
    (source / "release-notes.md").write_text("# Release notes\n", encoding="utf-8")

    out_path = tmp_path / "chunks" / "chunks.jsonl"
    stats_path = tmp_path / "chunks" / "stats.json"
    config = make_config()

    stats = build_corpus(source, out_path, stats_path, config)

    lines = out_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == stats.chunks
    assert stats.files == 2
    assert stats.skipped == 1
    assert stats.chunks > 0
    assert stats.tokens > 0
    assert stats.min_tokens is not None
    assert stats.max_tokens >= stats.min_tokens

    first = json.loads(lines[0])
    assert first["path"] == "index.md"
    assert first["url"] == "https://example.com/"
    assert first["version"] == "test-ref"
    assert first["title"] == "Home"

    saved_stats = json.loads(stats_path.read_text(encoding="utf-8"))
    assert saved_stats["files"] == 2
    assert saved_stats["skipped"] == 1
    assert saved_stats["chunks"] == stats.chunks
    assert saved_stats["sections"]["root"] > 0
    assert saved_stats["sections"]["tutorial"] > 0
