from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Self

from pydantic import BaseModel, Field, model_validator


class CorpusConfig(BaseModel):
    repo: str
    ref: str
    source_path: str = "docs/en/docs"
    docs_src_path: str = "docs_src"
    base_url: str
    language: str = "en"

    @property
    def project(self) -> str:
        return self.repo.rsplit("/", 1)[-1]


class FilteringConfig(BaseModel):
    excluded_paths: tuple[str, ...] = ()
    excluded_dirs: tuple[str, ...] = ()
    skip_underscore: bool = True


class ChunkingConfig(BaseModel):
    max_tokens: int = Field(default=350, gt=0)
    overlap_tokens: int = Field(default=50, ge=0)
    heading_separator: str = " > "
    code_ratio_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    resolve_docs_src: bool = True

    @model_validator(mode="after")
    def validate_overlap(self) -> Self:
        if self.overlap_tokens >= self.max_tokens:
            raise ValueError("overlap_tokens must be less than max_tokens")
        return self


class OutputConfig(BaseModel):
    chunks_dir: str = "chunks"
    chunks_filename: str = "chunks.jsonl"
    stats_filename: str = "stats.json"


class IngestionConfig(BaseModel):
    corpus: CorpusConfig
    filtering: FilteringConfig
    chunking: ChunkingConfig
    output: OutputConfig


def load_ingestion_config(path: Path) -> IngestionConfig:
    if not path.exists():
        raise FileNotFoundError(f"Ingestion config not found: {path}")
    with path.open("rb") as file:
        data = tomllib.load(file)
    return IngestionConfig.model_validate(data)
