# Конфигурация

## Два слоя конфигурации

| Слой | Файл | Что хранит |
|---|---|---|
| Runtime и секреты | `.env` | Qdrant, модели, retrieval, LLM, логирование, Docker |
| Корпус и чанкинг | `config/ingestion.toml` | Источник docs, фильтры, размеры чанков, output paths |

`Settings` читает `.env` через Pydantic Settings. `IngestionConfig` читает TOML через
stdlib `tomllib`. CLI-флаги переопределяют значения TOML для конкретного запуска.

## config/ingestion.toml

### `[corpus]`

| Ключ | По умолчанию | Описание |
|---|---|---|
| `repo` | `fastapi/fastapi` | GitHub-репозиторий |
| `ref` | pinned SHA | Commit, branch или tag |
| `source_path` | `docs/en/docs` | Путь к Markdown-докам внутри архива |
| `docs_src_path` | `docs_src` | Путь к примерам кода для include-директив |
| `base_url` | `https://fastapi.tiangolo.com` | База для URL цитат |
| `language` | `en` | Язык корпуса |

### `[filtering]`

| Ключ | Описание |
|---|---|
| `excluded_paths` | Точные относительные пути, которые не индексируются |
| `excluded_dirs` | Директории, которые пропускаются целиком |
| `skip_underscore` | Пропускать файлы, начинающиеся с `_` |

### `[chunking]`

| Ключ | По умолчанию | Описание |
|---|---|---|
| `max_tokens` | `350` | Жёсткий лимит размера чанка |
| `overlap_tokens` | `50` | Overlap между чанками |
| `heading_separator` | ` > ` | Разделитель heading path |
| `code_ratio_threshold` | `0.6` | Доля code-токенов для `content_type=code` |
| `resolve_docs_src` | `true` | Подставлять код из `docs_src` вместо include-директив |

`overlap_tokens` обязан быть меньше `max_tokens`.

### `[output]`

| Ключ | По умолчанию | Описание |
|---|---|---|
| `chunks_dir` | `chunks` | Поддиректория внутри `DATA_DIR` |
| `chunks_filename` | `chunks.jsonl` | Имя JSONL с чанками |
| `stats_filename` | `stats.json` | Имя файла статистики |

## Переменные `.env`

### Приложение и логи

| Переменная | По умолчанию | Описание |
|---|---|---|
| `APP_NAME` | `DocsLens` | Имя приложения |
| `ENVIRONMENT` | `local` | `local`, `test`, `production` |
| `LOG_LEVEL` | `INFO` | Уровень structlog |
| `LOG_FORMAT` | `json` | `json` или `console` |
| `DATA_DIR` | `data` | Корень для raw/chunks |
| `INGESTION_CONFIG` | `config/ingestion.toml` | Путь к TOML |
| `DOCS_ARCHIVE_URL_TEMPLATE` | GitHub archive URL | Шаблон `{repo}` / `{ref}` |
| `DOWNLOAD_TIMEOUT` | `120` | Таймаут скачивания архива, секунды |

### Qdrant и индексация

| Переменная | По умолчанию | Описание |
|---|---|---|
| `QDRANT_URL` | `http://localhost:6333` | HTTP endpoint |
| `QDRANT_API_KEY` | пусто | Ключ Qdrant Cloud |
| `QDRANT_COLLECTION` | `fastapi_docs` | Имя коллекции |
| `QDRANT_TIMEOUT` | `30` | Таймаут клиента |
| `QDRANT_DISTANCE` | `cosine` | `cosine`, `dot`, `euclid` |
| `DENSE_VECTOR_NAME` | `dense` | Имя dense-вектора |
| `SPARSE_VECTOR_NAME` | `sparse` | Имя sparse-вектора |
| `PAYLOAD_INDEX_FIELDS` | JSON-массив полей | Поля payload-индексов |
| `INDEX_BATCH_SIZE` | `32` | Размер батча индексации |

При смене имён векторов или distance нужен `index --recreate`.

### Dense и sparse embeddings

| Переменная | По умолчанию | Описание |
|---|---|---|
| `EMBEDDING_MODEL` | `intfloat/multilingual-e5-base` | Dense-модель |
| `EMBEDDING_DEVICE` | `cpu` | `cpu` или `cuda` |
| `EMBEDDING_BATCH_SIZE` | `32` | Батч эмбеддингов |
| `DENSE_QUERY_PREFIX` | `query: ` | Префикс запроса e5 |
| `DENSE_PASSAGE_PREFIX` | `passage: ` | Префикс документа e5 |
| `NORMALIZE_EMBEDDINGS` | `true` | L2-нормализация |
| `SPARSE_MODEL` | `Qdrant/bm25` | Sparse-модель FastEmbed |
| `SPARSE_LANGUAGE` | `english` | Язык BM25-стеммера |

### Retrieval

| Переменная | По умолчанию | Описание |
|---|---|---|
| `RETRIEVAL_CANDIDATES` | `30` | Кандидатов на ветку для RRF |
| `RETRIEVAL_TOP_K` | `5` | Результатов по умолчанию |
| `RETRIEVAL_DEFAULT_MODE` | `hybrid` | `dense`, `sparse`, `hybrid` |
| `RERANK_ENABLED` | `true` | Задел на этап 4 |
| `RERANK_MODEL` | `BAAI/bge-reranker-v2-m3` | Задел на этап 4 |

### LLM

| Переменная | По умолчанию | Описание |
|---|---|---|
| `LLM_MODE` | `openrouter` | `openrouter` или `fake` |
| `LLM_BASE_URL` | OpenRouter URL | OpenAI-compatible endpoint |
| `LLM_API_KEY` | пусто | Ключ OpenRouter |
| `LLM_MODEL` | `deepseek/deepseek-chat` | ID модели |

LLM пока не используется; генерация ответов появится на этапе 4.

### API и UI

| Переменная | По умолчанию | Описание |
|---|---|---|
| `CORS_ORIGINS` | `["http://localhost:8501"]` | JSON-массив разрешённых origins |
| `UI_API_URL` | `http://localhost:8000` | URL API для Streamlit |
| `SEARCH_MAX_TOP_K` | `20` | Верхняя граница `top_k` в `/api/search` |
| `QUERY_MAX_LENGTH` | `500` | Максимальная длина запроса в символах |

`CORS_ORIGINS` задаётся JSON-массивом, как `PAYLOAD_INDEX_FIELDS`:

```dotenv
CORS_ORIGINS=["http://localhost:8501","http://127.0.0.1:8501"]
```

### Docker Compose

| Переменная | По умолчанию |
|---|---|
| `QDRANT_IMAGE` | `qdrant/qdrant:v1.19.2` |
| `QDRANT_HTTP_PORT` | `6333` |
| `QDRANT_GRPC_PORT` | `6334` |
| `API_PORT` | `8000` |
| `PYTHON_VERSION` | `3.12` |
| `UV_VERSION` | `0.13.4` |

## CLI-переопределения

Ingestion-команды принимают `--config`, `--repo`, `--ref`, `--base-url`,
`--language`, `--max-tokens`, `--overlap-tokens`, `--source`, `--out`, `--stats`,
`--data-dir`.

Приоритет: CLI-флаг → `config/ingestion.toml` → значение по умолчанию.
`INGESTION_CONFIG` задаёт TOML-файл, если `--config` не передан.
