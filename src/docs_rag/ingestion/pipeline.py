import json
from dataclasses import dataclass, field
from pathlib import Path

import structlog

from docs_rag.config import Settings
from docs_rag.ingestion.chunker import chunk_document
from docs_rag.ingestion.filters import is_indexable
from docs_rag.ingestion.includes import resolve_includes
from docs_rag.ingestion.models import Chunk, DocFile
from docs_rag.ingestion.tokens import RegexTokenCounter, TokenCounter
from docs_rag.ingestion.urls import doc_url, section_for_path

logger = structlog.get_logger(__name__)


@dataclass
class CorpusStats:
    files: int = 0
    skipped: int = 0
    chunks: int = 0
    tokens: int = 0
    min_tokens: int | None = None
    max_tokens: int = 0
    content_types: dict[str, int] = field(default_factory=dict)
    sections: dict[str, int] = field(default_factory=dict)

    def add(self, chunk: Chunk) -> None:
        self.chunks += 1
        self.tokens += chunk.token_count
        self.min_tokens = (
            chunk.token_count
            if self.min_tokens is None
            else min(self.min_tokens, chunk.token_count)
        )
        self.max_tokens = max(self.max_tokens, chunk.token_count)
        self.content_types[chunk.content_type] = self.content_types.get(chunk.content_type, 0) + 1
        self.sections[chunk.section] = self.sections.get(chunk.section, 0) + 1

    def to_dict(self) -> dict[str, object]:
        average = round(self.tokens / self.chunks, 2) if self.chunks else 0.0
        return {
            "files": self.files,
            "skipped": self.skipped,
            "chunks": self.chunks,
            "tokens": self.tokens,
            "avg_tokens": average,
            "min_tokens": self.min_tokens,
            "max_tokens": self.max_tokens,
            "content_types": dict(sorted(self.content_types.items())),
            "sections": dict(sorted(self.sections.items())),
        }


def collect_docs(source_dir: Path, base_url: str) -> tuple[list[DocFile], int]:
    docs: list[DocFile] = []
    skipped = 0

    for path in sorted(source_dir.rglob("*.md")):
        relative_path = path.relative_to(source_dir).as_posix()
        if not is_indexable(relative_path):
            skipped += 1
            continue

        docs.append(
            DocFile(
                relative_path=relative_path,
                text=resolve_includes(
                    path.read_text(encoding="utf-8"),
                    source_dir,
                ),
                url=doc_url(relative_path, base_url),
                title=Path(relative_path).stem,
                section=section_for_path(relative_path),
            )
        )

    return docs, skipped


def chunk_documents(
    docs: list[DocFile],
    settings: Settings,
    counter: TokenCounter,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    for doc in docs:
        chunks.extend(chunk_document(doc, settings, counter))
    return chunks


def build_corpus(
    source_dir: Path,
    out_path: Path,
    stats_path: Path,
    settings: Settings,
    counter: TokenCounter | None = None,
) -> CorpusStats:
    token_counter = counter or RegexTokenCounter()
    docs, skipped = collect_docs(source_dir, settings.docs_base_url)
    chunks = chunk_documents(docs, settings, token_counter)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="\n") as output:
        for chunk in chunks:
            output.write(json.dumps(chunk.to_dict(), ensure_ascii=False))
            output.write("\n")

    stats = CorpusStats(files=len(docs), skipped=skipped)
    for chunk in chunks:
        stats.add(chunk)

    stats_path.parent.mkdir(parents=True, exist_ok=True)
    stats_path.write_text(
        json.dumps(stats.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    logger.info(
        "corpus_built",
        files=stats.files,
        skipped=stats.skipped,
        chunks=stats.chunks,
        tokens=stats.tokens,
        out=str(out_path),
        stats=str(stats_path),
    )
    return stats
