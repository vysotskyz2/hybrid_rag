from __future__ import annotations

import shutil
import tarfile
import urllib.request
from pathlib import Path, PurePosixPath

import structlog

from docs_rag import __version__
from docs_rag.ingestion.config import IngestionConfig

logger = structlog.get_logger(__name__)

USER_AGENT = f"docs-rag/{__version__}"


def archive_url(repo: str, ref: str, template: str) -> str:
    return template.format(repo=repo, ref=ref)


def download_archive(
    url: str,
    dest: Path,
    timeout: int = 120,
    force: bool = False,
) -> Path:
    if dest.exists() and dest.stat().st_size > 0 and not force:
        logger.info("archive_cached", path=str(dest))
        return dest

    dest.parent.mkdir(parents=True, exist_ok=True)
    temporary = dest.with_name(f"{dest.name}.part")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    logger.info("archive_download_start", url=url)

    with (
        urllib.request.urlopen(request, timeout=timeout) as response,
        temporary.open("wb") as output,
    ):
        while chunk := response.read(1024 * 1024):
            output.write(chunk)

    temporary.replace(dest)
    logger.info("archive_download_done", path=str(dest), bytes=dest.stat().st_size)
    return dest


def extract_docs(
    archive: Path,
    dest: Path,
    prefix: str,
    archive_prefix: str | None = None,
    force: bool = False,
) -> list[Path]:
    if dest.exists() and force:
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    marker = f"/{prefix.strip('/')}/"
    extracted: list[Path] = []
    expected_root = archive_prefix.strip("/") if archive_prefix else None

    with tarfile.open(archive, mode="r:gz") as tar:
        for member in tar:
            if not member.isfile():
                continue
            if expected_root is not None and not member.name.startswith(expected_root):
                continue

            marker_index = member.name.find(marker)
            if marker_index < 0:
                continue

            relative = PurePosixPath(member.name[marker_index + len(marker) :])
            if relative.is_absolute() or ".." in relative.parts:
                continue
            if relative.suffix.lower() != ".md":
                continue

            source = tar.extractfile(member)
            if source is None:
                continue

            target = dest.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read())
            extracted.append(target)

    logger.info("docs_extracted", files=len(extracted), dest=str(dest))
    return extracted


def extract_docs_sources(
    archive: Path,
    dest: Path,
    source_path: str = "docs_src",
    archive_prefix: str | None = None,
) -> list[Path]:
    marker = f"/{source_path.strip('/')}/"
    dest_root = dest / source_path
    dest_root.mkdir(parents=True, exist_ok=True)
    expected_root = archive_prefix.strip("/") if archive_prefix else None
    extracted: list[Path] = []

    with tarfile.open(archive, mode="r:gz") as tar:
        for member in tar:
            if not member.isfile():
                continue
            if expected_root is not None and not member.name.startswith(expected_root):
                continue

            marker_index = member.name.find(marker)
            if marker_index < 0:
                continue

            relative = PurePosixPath(member.name[marker_index + len(marker) :])
            if relative.is_absolute() or ".." in relative.parts:
                continue

            source = tar.extractfile(member)
            if source is None:
                continue

            target = dest_root.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read())
            extracted.append(target)

    logger.info("docs_sources_extracted", files=len(extracted), dest=str(dest_root))
    return extracted


def fetch_docs(
    config: IngestionConfig,
    data_dir: Path,
    archive_url_template: str,
    timeout: int = 120,
    force: bool = False,
) -> Path:
    corpus = config.corpus
    project = corpus.project
    safe_ref = corpus.ref.replace("/", "-")
    dest = data_dir / "raw" / f"{project}-docs" / safe_ref
    archive = data_dir / "raw" / f"{project}-{safe_ref}.tar.gz"
    archive_prefix = f"{project}-"

    if dest.exists() and any(dest.rglob("*.md")) and not force:
        if not (dest / corpus.docs_src_path).exists():
            if not archive.exists():
                download_archive(
                    archive_url(corpus.repo, corpus.ref, archive_url_template),
                    archive,
                    timeout=timeout,
                )
            extract_docs_sources(
                archive,
                dest,
                source_path=corpus.docs_src_path,
                archive_prefix=archive_prefix,
            )
        logger.info("docs_cached", path=str(dest))
        return dest

    download_archive(
        archive_url(corpus.repo, corpus.ref, archive_url_template),
        archive,
        timeout=timeout,
        force=force,
    )
    extract_docs(
        archive,
        dest,
        prefix=corpus.source_path,
        archive_prefix=archive_prefix,
        force=force,
    )
    extract_docs_sources(
        archive,
        dest,
        source_path=corpus.docs_src_path,
        archive_prefix=archive_prefix,
    )
    return dest
