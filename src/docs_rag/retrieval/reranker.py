from __future__ import annotations

import time
from dataclasses import replace
from typing import TYPE_CHECKING

import structlog

from docs_rag.config import Settings
from docs_rag.retrieval.models import SearchResult

if TYPE_CHECKING:
    from sentence_transformers import CrossEncoder

logger = structlog.get_logger(__name__)


class CrossEncoderReranker:
    def __init__(
        self,
        model_name: str,
        device: str = "cpu",
        batch_size: int = 8,
        max_length: int = 512,
        model: CrossEncoder | None = None,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if max_length <= 0:
            raise ValueError("max_length must be positive")

        if model is None:
            from sentence_transformers import CrossEncoder

            model = CrossEncoder(
                model_name,
                device=device,
                max_length=max_length,
            )

        self._model = model
        self._model_name = model_name
        self._batch_size = batch_size
        self._max_length = max_length

    @property
    def model_name(self) -> str:
        return self._model_name

    def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int,
    ) -> list[SearchResult]:
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        if not results:
            return []

        started = time.perf_counter()
        documents = [result.text for result in results]
        ranked = self._model.rank(
            query,
            documents,
            top_k=min(top_k, len(documents)),
            batch_size=self._batch_size,
            show_progress_bar=False,
        )

        reranked = []
        for item in ranked:
            index = int(item["corpus_id"])
            original = results[index]
            reranked.append(
                replace(
                    original,
                    score=float(item["score"]),
                    retrieval_score=original.score,
                )
            )

        logger.info(
            "rerank_completed",
            candidates=len(results),
            returned=len(reranked),
            elapsed_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        return reranked


def build_reranker(settings: Settings) -> CrossEncoderReranker | None:
    if not settings.rerank_enabled:
        return None
    return CrossEncoderReranker(
        model_name=settings.rerank_model,
        device=settings.embedding_device,
        batch_size=settings.rerank_batch_size,
        max_length=settings.rerank_max_length,
    )
