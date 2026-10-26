from qdrant_client import models

from docs_rag.retrieval.models import SearchFilters

FILTER_FIELDS = ("section", "content_type", "language", "version", "path")


def build_qdrant_filter(filters: SearchFilters | None) -> models.Filter | None:
    if filters is None:
        return None

    conditions: list[models.FieldCondition] = []
    for field_name in FILTER_FIELDS:
        value = getattr(filters, field_name)
        if value:
            conditions.append(
                models.FieldCondition(
                    key=field_name,
                    match=models.MatchValue(value=value),
                )
            )

    return models.Filter(must=conditions) if conditions else None
