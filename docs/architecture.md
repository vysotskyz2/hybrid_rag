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

- **Ingestion** — загрузка Markdown-документации, фильтрация служебных страниц, чанкинг по структуре заголовков.
- **Retrieval** — Qdrant с двумя named vectors: dense и sparse.
- **Fusion** — RRF поверх dense- и BM25-кандидатов.
- **Reranking** — cross-encoder для финального top-k.
- **Generation** — ответ только по найденному контексту, с цитатами на разделы документации.
- **API** — FastAPI с SSE-стримингом.
- **UI** — Streamlit: чат и сравнение режимов поиска.

## Принципы

- `main` обновляется только через merge веток этапов.
- Секреты живут только в `.env`.
- Тесты не требуют API-ключа: LLM подменяется заглушкой.
- Все результаты eval воспроизводимы и хранятся в репозитории.
