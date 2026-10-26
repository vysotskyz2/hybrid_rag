import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from docs_rag import __version__
from docs_rag.config import Settings, get_settings
from docs_rag.ingestion.config import IngestionConfig, load_ingestion_config
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


def _add_config_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Ingestion TOML config",
    )


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
    parser.add_argument("--max-tokens", type=int, default=None)
    parser.add_argument("--overlap-tokens", type=int, default=None)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="docs-rag")
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command")

    fetch_parser = subparsers.add_parser("fetch", help="Download and extract docs")
    _add_config_option(fetch_parser)
    _add_fetch_options(fetch_parser)
    fetch_parser.set_defaults(func=_cmd_fetch)

    chunk_parser = subparsers.add_parser("chunk", help="Build chunks from extracted docs")
    _add_config_option(chunk_parser)
    _add_chunk_options(chunk_parser)
    chunk_parser.add_argument("--ref", default=None, help="Corpus version label")
    chunk_parser.add_argument("--data-dir", type=Path, default=None, help="Data directory")
    chunk_parser.set_defaults(func=_cmd_chunk)

    ingest_parser = subparsers.add_parser("ingest", help="Fetch docs and build chunks")
    _add_config_option(ingest_parser)
    _add_fetch_options(ingest_parser)
    _add_chunk_options(ingest_parser)
    ingest_parser.set_defaults(func=_cmd_ingest)

    index_parser = subparsers.add_parser(
        "index",
        help="Embed chunks and upsert them into Qdrant",
    )
    _add_config_option(index_parser)
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
        default=None,
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


def _load_config(args: argparse.Namespace, settings: Settings) -> IngestionConfig:
    path = args.config if args.config is not None else settings.ingestion_config
    return load_ingestion_config(path)


def _apply_ingestion_overrides(
    args: argparse.Namespace,
    config: IngestionConfig,
) -> IngestionConfig:
    corpus_updates: dict[str, Any] = {}
    for field_name in ("repo", "ref", "base_url", "language"):
        value = getattr(args, field_name, None)
        if value is not None:
            corpus_updates[field_name] = value

    chunking_updates: dict[str, Any] = {}
    for field_name in ("max_tokens", "overlap_tokens"):
        value = getattr(args, field_name, None)
        if value is not None:
            chunking_updates[field_name] = value

    return config.model_copy(
        update={
            "corpus": config.corpus.model_copy(update=corpus_updates),
            "chunking": config.chunking.model_copy(update=chunking_updates),
        }
    )


def _resolve_data_dir(args: argparse.Namespace, settings: Settings) -> Path:
    data_dir: Path | None = getattr(args, "data_dir", None)
    return data_dir if data_dir is not None else settings.data_dir


def _resolve_source(data_dir: Path, config: IngestionConfig) -> Path:
    safe_ref = config.corpus.ref.replace("/", "-")
    return data_dir / "raw" / f"{config.corpus.project}-docs" / safe_ref


def _resolve_output_paths(
    args: argparse.Namespace,
    data_dir: Path,
    config: IngestionConfig,
) -> tuple[Path, Path]:
    chunks_dir = data_dir / config.output.chunks_dir
    out = args.out if args.out is not None else chunks_dir / config.output.chunks_filename
    stats = args.stats if args.stats is not None else chunks_dir / config.output.stats_filename
    return out, stats


def _run_chunk(
    source: Path,
    out: Path,
    stats_path: Path,
    config: IngestionConfig,
) -> CorpusStats:
    if not source.exists():
        raise SystemExit(f"Docs source not found: {source}")
    return build_corpus(
        source_dir=source,
        out_path=out,
        stats_path=stats_path,
        config=config,
    )


def _print_stats(stats: CorpusStats) -> None:
    print(json.dumps(stats.to_dict(), indent=2, ensure_ascii=False))


def _cmd_fetch(args: argparse.Namespace, settings: Settings) -> None:
    data_dir = _resolve_data_dir(args, settings)
    config = _apply_ingestion_overrides(args, _load_config(args, settings))
    source = fetch_docs(
        config=config,
        data_dir=data_dir,
        archive_url_template=settings.docs_archive_url_template,
        timeout=settings.download_timeout,
        force=args.force,
    )
    files = sum(1 for _ in source.rglob("*.md"))
    print(json.dumps({"source": str(source), "files": files}, indent=2))


def _cmd_chunk(args: argparse.Namespace, settings: Settings) -> None:
    data_dir = _resolve_data_dir(args, settings)
    config = _apply_ingestion_overrides(args, _load_config(args, settings))
    source = args.source or _resolve_source(data_dir, config)
    out, stats_path = _resolve_output_paths(args, data_dir, config)
    stats = _run_chunk(source, out, stats_path, config)
    _print_stats(stats)


def _cmd_ingest(args: argparse.Namespace, settings: Settings) -> None:
    data_dir = _resolve_data_dir(args, settings)
    config = _apply_ingestion_overrides(args, _load_config(args, settings))
    source = fetch_docs(
        config=config,
        data_dir=data_dir,
        archive_url_template=settings.docs_archive_url_template,
        timeout=settings.download_timeout,
        force=args.force,
    )
    out, stats_path = _resolve_output_paths(args, data_dir, config)
    stats = _run_chunk(source, out, stats_path, config)
    _print_stats(stats)


def _cmd_index(args: argparse.Namespace, settings: Settings) -> None:
    data_dir = _resolve_data_dir(args, settings)
    config = _load_config(args, settings)
    chunks_path = (
        args.chunks
        if args.chunks is not None
        else data_dir / config.output.chunks_dir / config.output.chunks_filename
    )
    if not chunks_path.exists():
        raise SystemExit(f"Chunks file not found: {chunks_path}")

    chunks = load_chunks(chunks_path)
    if not chunks:
        raise SystemExit(f"No chunks found in: {chunks_path}")

    dense = SentenceTransformerDenseEmbedder(
        model_name=settings.embedding_model,
        device=settings.embedding_device,
        batch_size=settings.embedding_batch_size,
        query_prefix=settings.dense_query_prefix,
        passage_prefix=settings.dense_passage_prefix,
        normalize=settings.normalize_embeddings,
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
        query_prefix=settings.dense_query_prefix,
        passage_prefix=settings.dense_passage_prefix,
        normalize=settings.normalize_embeddings,
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
            mode=args.mode or settings.retrieval_default_mode,
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
    configure_logging(settings.log_level, settings.log_format)
    args.func(args, settings)


if __name__ == "__main__":
    main()
