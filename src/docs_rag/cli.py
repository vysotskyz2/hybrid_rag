import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from docs_rag import __version__
from docs_rag.config import Settings, get_settings
from docs_rag.ingestion.fetch import fetch_docs
from docs_rag.ingestion.pipeline import CorpusStats, build_corpus
from docs_rag.logging import configure_logging
from docs_rag.retrieval.embeddings import (
    FastEmbedSparseEmbedder,
    SentenceTransformerDenseEmbedder,
)
from docs_rag.retrieval.indexer import build_index, load_chunks
from docs_rag.retrieval.models import SearchFilters
from docs_rag.retrieval.search import Retriever
from docs_rag.retrieval.store import QdrantStore


def _add_fetch_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo", default=None, help="GitHub repository, e.g. fastapi/fastapi")
    parser.add_argument("--ref", default=None, help="Commit SHA, branch, or tag")
    parser.add_argument("--data-dir", type=Path, default=None, help="Data directory")
    parser.add_argument("--force", action="store_true", help="Re-download and re-extract")


def _add_chunk_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--source", type=Path, default=None, help="Extracted docs directory")
    parser.add_argument("--out", type=Path, default=None, help="Output JSONL path")
    parser.add_argument("--stats", type=Path, default=None, help="Output stats JSON path")
    parser.add_argument("--base-url", default=None, help="Documentation site base URL")
    parser.add_argument("--language", default=None, help="Corpus language code")
    parser.add_argument("--target-tokens", type=int, default=None)
    parser.add_argument("--max-tokens", type=int, default=None)
    parser.add_argument("--overlap-tokens", type=int, default=None)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="docs-rag")
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command")

    fetch_parser = subparsers.add_parser("fetch", help="Download and extract FastAPI docs")
    _add_fetch_options(fetch_parser)
    fetch_parser.set_defaults(func=_cmd_fetch)

    chunk_parser = subparsers.add_parser("chunk", help="Build chunks from extracted docs")
    _add_chunk_options(chunk_parser)
    chunk_parser.add_argument("--ref", default=None, help="Corpus version label")
    chunk_parser.add_argument("--data-dir", type=Path, default=None, help="Data directory")
    chunk_parser.set_defaults(func=_cmd_chunk)

    ingest_parser = subparsers.add_parser("ingest", help="Fetch docs and build chunks")
    _add_fetch_options(ingest_parser)
    _add_chunk_options(ingest_parser)
    ingest_parser.set_defaults(func=_cmd_ingest)

    index_parser = subparsers.add_parser(
        "index",
        help="Embed chunks and upsert them into Qdrant",
    )
    index_parser.add_argument("--chunks", type=Path, default=None, help="Chunks JSONL path")
    index_parser.add_argument("--data-dir", type=Path, default=None, help="Data directory")
    index_parser.add_argument("--batch-size", type=int, default=None)
    index_parser.add_argument("--recreate", action="store_true", help="Recreate collection")
    index_parser.set_defaults(func=_cmd_index)

    search_parser = subparsers.add_parser("search", help="Search the Qdrant index")
    search_parser.add_argument("--query", required=True)
    search_parser.add_argument(
        "--mode",
        choices=("dense", "sparse", "hybrid"),
        default="hybrid",
    )
    search_parser.add_argument("--top-k", type=int, default=None)
    search_parser.add_argument("--candidates", type=int, default=None)
    search_parser.add_argument("--section", default=None)
    search_parser.add_argument(
        "--content-type",
        choices=("prose", "code", "mixed"),
        default=None,
    )
    search_parser.add_argument("--language", default=None)
    search_parser.add_argument("--version", default=None)
    search_parser.set_defaults(func=_cmd_search)

    return parser


def _resolve_data_dir(args: argparse.Namespace, settings: Settings) -> Path:
    data_dir: Path | None = args.data_dir
    return data_dir if data_dir is not None else settings.data_dir


def _resolve_source(data_dir: Path, ref: str) -> Path:
    return data_dir / "raw" / "fastapi-docs" / ref.replace("/", "-")


def _chunk_settings(args: argparse.Namespace, settings: Settings) -> Settings:
    updates: dict[str, Any] = {
        "docs_base_url": args.base_url or settings.docs_base_url,
        "docs_language": args.language or settings.docs_language,
    }
    if args.ref:
        updates["docs_ref"] = args.ref
    if args.target_tokens is not None:
        updates["chunk_target_tokens"] = args.target_tokens
    if args.max_tokens is not None:
        updates["chunk_max_tokens"] = args.max_tokens
    if args.overlap_tokens is not None:
        updates["chunk_overlap_tokens"] = args.overlap_tokens
    return settings.model_copy(update=updates)


def _run_chunk(
    source: Path,
    out: Path,
    stats_path: Path,
    args: argparse.Namespace,
    settings: Settings,
) -> CorpusStats:
    if not source.exists():
        raise SystemExit(f"Docs source not found: {source}")
    return build_corpus(
        source_dir=source,
        out_path=out,
        stats_path=stats_path,
        settings=_chunk_settings(args, settings),
    )


def _print_stats(stats: CorpusStats) -> None:
    print(json.dumps(stats.to_dict(), indent=2, ensure_ascii=False))


def _cmd_fetch(args: argparse.Namespace, settings: Settings) -> None:
    data_dir = _resolve_data_dir(args, settings)
    repo = args.repo or settings.docs_repo
    ref = args.ref or settings.docs_ref
    source = fetch_docs(
        repo=repo,
        ref=ref,
        data_dir=data_dir,
        source_path=settings.docs_source_path,
        force=args.force,
    )
    files = sum(1 for _ in source.rglob("*.md"))
    print(json.dumps({"source": str(source), "files": files}, indent=2))


def _cmd_chunk(args: argparse.Namespace, settings: Settings) -> None:
    data_dir = _resolve_data_dir(args, settings)
    ref = args.ref or settings.docs_ref
    source = args.source or _resolve_source(data_dir, ref)
    out = args.out or data_dir / "chunks" / "chunks.jsonl"
    stats_path = args.stats or data_dir / "chunks" / "stats.json"
    stats = _run_chunk(source, out, stats_path, args, settings)
    _print_stats(stats)


def _cmd_ingest(args: argparse.Namespace, settings: Settings) -> None:
    data_dir = _resolve_data_dir(args, settings)
    repo = args.repo or settings.docs_repo
    ref = args.ref or settings.docs_ref
    source = fetch_docs(
        repo=repo,
        ref=ref,
        data_dir=data_dir,
        source_path=settings.docs_source_path,
        force=args.force,
    )
    out = args.out or data_dir / "chunks" / "chunks.jsonl"
    stats_path = args.stats or data_dir / "chunks" / "stats.json"
    stats = _run_chunk(source, out, stats_path, args, settings)
    _print_stats(stats)


def _cmd_index(args: argparse.Namespace, settings: Settings) -> None:
    data_dir = _resolve_data_dir(args, settings)
    chunks_path = args.chunks or data_dir / "chunks" / "chunks.jsonl"
    if not chunks_path.exists():
        raise SystemExit(f"Chunks file not found: {chunks_path}")

    chunks = load_chunks(chunks_path)
    if not chunks:
        raise SystemExit(f"No chunks found in: {chunks_path}")

    dense = SentenceTransformerDenseEmbedder(
        model_name=settings.embedding_model,
        device=settings.embedding_device,
        batch_size=settings.embedding_batch_size,
    )
    sparse = FastEmbedSparseEmbedder(
        model_name=settings.sparse_model,
        language=settings.sparse_language,
        batch_size=settings.embedding_batch_size,
    )
    store = QdrantStore.from_settings(settings)
    try:
        stats = build_index(
            chunks=chunks,
            store=store,
            dense=dense,
            sparse=sparse,
            version=chunks[0].version,
            batch_size=(
                args.batch_size if args.batch_size is not None else settings.index_batch_size
            ),
            recreate=args.recreate,
        )
        print(json.dumps(stats.to_dict(), indent=2, ensure_ascii=False))
    finally:
        store.close()


def _cmd_search(args: argparse.Namespace, settings: Settings) -> None:
    dense = SentenceTransformerDenseEmbedder(
        model_name=settings.embedding_model,
        device=settings.embedding_device,
        batch_size=settings.embedding_batch_size,
    )
    sparse = FastEmbedSparseEmbedder(
        model_name=settings.sparse_model,
        language=settings.sparse_language,
        batch_size=settings.embedding_batch_size,
    )
    store = QdrantStore.from_settings(settings)
    try:
        retriever = Retriever(
            store=store,
            dense=dense,
            sparse=sparse,
            candidates=(
                args.candidates if args.candidates is not None else settings.retrieval_candidates
            ),
        )
        results = retriever.search(
            query=args.query,
            mode=args.mode,
            top_k=(args.top_k if args.top_k is not None else settings.retrieval_top_k),
            filters=SearchFilters(
                section=args.section,
                content_type=args.content_type,
                language=args.language,
                version=args.version,
            ),
        )
        print(
            json.dumps(
                [result.to_dict() for result in results],
                indent=2,
                ensure_ascii=False,
            )
        )
    finally:
        store.close()


def main(argv: Sequence[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return

    settings = get_settings()
    configure_logging(settings.log_level)
    args.func(args, settings)


if __name__ == "__main__":
    main()
