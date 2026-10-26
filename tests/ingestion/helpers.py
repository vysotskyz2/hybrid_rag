from pathlib import Path

from docs_rag.ingestion.config import (
    ChunkingConfig,
    CorpusConfig,
    FilteringConfig,
    IngestionConfig,
    load_ingestion_config,
)

CONFIG_PATH = Path(__file__).parents[2] / "config" / "ingestion.toml"


def make_config(
    *,
    chunking: ChunkingConfig | None = None,
    corpus: CorpusConfig | None = None,
    filtering: FilteringConfig | None = None,
) -> IngestionConfig:
    base = load_ingestion_config(CONFIG_PATH)
    return base.model_copy(
        update={
            "corpus": corpus
            or base.corpus.model_copy(
                update={
                    "ref": "test-ref",
                    "base_url": "https://example.com",
                }
            ),
            "filtering": filtering or base.filtering,
            "chunking": chunking or base.chunking,
        }
    )
