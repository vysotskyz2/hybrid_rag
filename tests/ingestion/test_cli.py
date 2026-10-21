import json
from pathlib import Path

from docs_rag.cli import main


def test_chunk_command_writes_output(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "index.md").write_text("# Home\n\nHello.\n", encoding="utf-8")

    out_path = tmp_path / "chunks.jsonl"
    stats_path = tmp_path / "stats.json"

    main(
        [
            "chunk",
            "--source",
            str(source),
            "--out",
            str(out_path),
            "--stats",
            str(stats_path),
            "--ref",
            "test-ref",
            "--base-url",
            "https://example.com",
        ]
    )

    assert out_path.exists()
    assert stats_path.exists()
    stats = json.loads(stats_path.read_text(encoding="utf-8"))
    assert stats["files"] == 1
    assert stats["chunks"] == 1
