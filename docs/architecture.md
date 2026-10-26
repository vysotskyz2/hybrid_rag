# Архитектура

## Поток данных

```mermaid
flowchart LR
    A[FastAPI docs<br/>pinned commit] --> B[Ingestion CLI]
    B --> C[Markdown parser<br/>structure-aware chunker]
    C --> D[Dense embeddings<br/>multilingual-e5-base]
    C --> E[Sparse BM25<br/>FastEmbed]
    D --> F[(Qdrant)]
    E --> F

    Q[Query RU/EN] --> G[Dense search]
    Q --> H[BM25 search]
    G --> F
    H --> F
    G --> I[RRF fusion]
    H --> I
    I --> J[Cross-encoder rerank]
    J --> K[Prompt with citations]
    K --> L[OpenRouter / DeepSeek]
    L --> M[SSE answer + sources]
    M --> N[Streamlit UI]
    M --> O[FastAPI API]
```

## Компоненты

- **Ingestion** — загрузка Markdown-документации по pinned commit, фильтрация служебных страниц, очистка frontmatter и HTML, чанкинг по структуре заголовков с сохранением code fences.
- **Retrieval** — Qdrant с двумя named vectors: dense и sparse.
- **Fusion** — RRF поверх dense- и BM25-кандидатов.
- **Reranking** — cross-encoder для финального top-k.
- **Generation** — ответ только по найденному контексту, с цитатами на разделы документации.
- **API** — FastAPI с SSE-стримингом.
- **UI** — Streamlit: чат и сравнение режимов поиска.

## Ingestion

```text
config/ingestion.toml
  → GitHub tarball @ pinned SHA
  → docs/en/docs/**/*.md + docs_src/**
  → filter + frontmatter/HTML cleanup + include resolution
  → heading-aware sections
  → block-based chunks (max 350 approx tokens, overlap 50)
  → data/chunks/chunks.jsonl + stats.json
```

Каждый чанк хранит `url`, `title`, `heading_path`, `section`, `content_type`,
`version`, `content_hash` и `token_count`. Это позволит на этапе retrieval
фильтровать по разделу и строить цитаты без дополнительных запросов.

## Retrieval

```text
query (RU/EN)
  ├─ e5 query embedding ──> dense search ─┐
  └─ BM25 query vector ───> sparse search ─┤
                                            ├─ RRF fusion ─> top-k
                                            └─ filters: section, content_type,
                                               language, version, path
```

Qdrant collection:

- `dense`: 768 dim, cosine, `multilingual-e5-base`;
- `sparse`: BM25 + IDF;
- point ID = UUID чанка;
- payload indexes по метаданным.

Индексация идемпотентна: повторный upsert обновляет точки по UUID, а stale points
удаляются после успешной записи. Полная пересборка — `--recreate`.



## Принципы

- `main` обновляется только через merge веток этапов.
- Секреты живут только в `.env`.
- Тесты не требуют API-ключа: LLM подменяется заглушкой.
- Все результаты eval воспроизводимы и хранятся в репозитории.
