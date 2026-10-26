from pathlib import Path

import pytest
from pydantic import ValidationError

from docs_rag.ingestion.config import ChunkingConfig, load_ingestion_config

CONFIG_PATH = Path(__file__).parents[2] / "config" / "ingestion.toml"


def test_load_ingestion_config() -> None:
    config = load_ingestion_config(CONFIG_PATH)

    assert config.corpus.repo == "fastapi/fastapi"
    assert config.corpus.project == "fastapi"
    assert config.corpus.ref == "68cc4cbb2e0600841b0d6bdd1cc29038b54a00e6"
    assert config.chunking.max_tokens == 350
    assert config.chunking.overlap_tokens == 50
    assert config.chunking.resolve_docs_src is True
    assert "release-notes.md" in config.filtering.excluded_paths
    assert config.output.chunks_filename == "chunks.jsonl"


def test_missing_config_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_ingestion_config(tmp_path / "missing.toml")


def test_overlap_must_be_less_than_max_tokens() -> None:
    with pytest.raises(ValidationError):
        ChunkingConfig(max_tokens=50, overlap_tokens=50)


def test_code_ratio_threshold_is_bounded() -> None:
    with pytest.raises(ValidationError):
        ChunkingConfig(code_ratio_threshold=1.5)
