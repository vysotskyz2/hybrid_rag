# DocsLens

Гибридный RAG-ассистент по документации FastAPI: BM25 + dense retrieval + cross-encoder reranker.

> Текущий статус: **этап 3 — API и UI**. Корпус собран, проиндексирован в Qdrant, работают dense, sparse и hybrid поиск через CLI, HTTP API и Streamlit. Reranker, генерация ответов и чат появятся в следующих ветках.

## Идея

Пользователь задаёт вопрос по-русски или по-английски и получает ответ на своём языке со ссылками на разделы документации FastAPI.

Гибридный поиск нужен, потому что у разных retriever'ов разные сильные стороны:

- BM25 находит точные API-имена: `Depends`, `HTTPException`, `background_tasks`;
- dense-поиск находит смысловые совпадения и работает между русским вопросом и английской документацией;
- cross-encoder reranker переупорядочивает кандидатов и повышает точность top-k.

## Стек

- Python 3.12, FastAPI, Pydantic v2
- Qdrant 1.19 с named vectors: dense + sparse
- `intfloat/multilingual-e5-base` для dense-эмбеддингов
- FastEmbed `Qdrant/bm25` для разреженного поиска
- `BAAI/bge-reranker-v2-m3` для reranking
- OpenRouter + DeepSeek для генерации
- Streamlit для демо-интерфейса
- uv, Docker Compose, GitHub Actions, ruff, mypy, pytest

## Быстрый старт

```powershell
uv sync
Copy-Item .env.example .env
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src
```

Поднять Qdrant и собрать индекс:

```powershell
docker compose up -d qdrant
uv run docs-rag ingest
uv run docs-rag index --recreate
```

Поиск:

```powershell
uv run docs-rag search --query "How do I use Depends?" --mode hybrid --top-k 5
uv run docs-rag search --query "Как работает внедрение зависимостей?" --mode hybrid
uv run docs-rag search --query "HTTPException" --mode sparse --top-k 3
```

Запустить API:

```powershell
uv run uvicorn docs_rag.api.main:app --reload
```

Swagger: http://127.0.0.1:8000/docs

Примеры запросов:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/ready
Invoke-RestMethod http://127.0.0.1:8000/api/stats

$body = @{
    query = "How do I use Depends?"
    mode = "hybrid"
    top_k = 3
    section = "tutorial"
    content_type = "prose"
} | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8000/api/search `
    -Method Post -ContentType "application/json" -Body $body
```

Запустить UI:

```powershell
uv run streamlit run ui/app.py
```

UI откроется на http://localhost:8501. Адрес API задаётся переменной `UI_API_URL`.

API в Docker:

```powershell
docker compose up --build api
```

## Ingestion

Источник — английская документация FastAPI, зафиксированная на commit
`68cc4cbb2e0600841b0d6bdd1cc29038b54a00e6`.

Pipeline:

1. Скачивает GitHub tarball по pinned SHA.
2. Извлекает `docs/en/docs/**/*.md` и `docs_src/**` с примерами кода.
3. Подставляет реальные примеры вместо MkDocs include-директив.
4. Убирает служебные страницы, frontmatter, HTML-комментарии/теги и спонсорские блоки.
5. Парсит заголовки и code fences.
6. Режет документ по секциям H1–H6, не разрывая code fences.
7. Сохраняет чанки с URL, заголовком, heading path и типом содержимого.

Текущий корпус:

| Метрика | Значение |
|---|---:|
| Документов | 143 |
| Пропущено служебных файлов | 13 |
| Файлов примеров из `docs_src` | 483 |
| Чанков | 1440 |
| Токенов (приблизительно) | 257 028 |
| Средний чанк | 178.49 |
| Максимальный чанк | 350 |
| Code / mixed / prose | 350 / 353 / 737 |

Подробности: [`docs/ingestion.md`](docs/ingestion.md).

## Конфигурация

Два слоя:

- `.env` — инфраструктура, секреты, модели, Qdrant, retrieval и LLM;
- `config/ingestion.toml` — источник документации, фильтры, параметры чанкинга и output paths.

CLI-флаги переопределяют TOML для конкретного запуска:

```powershell
uv run docs-rag ingest --config config/ingestion.toml --max-tokens 300
```

Полная таблица переменных и ключей: [`docs/configuration.md`](docs/configuration.md).

## Retrieval

Коллекция Qdrant `fastapi_docs`:

- dense vector: `multilingual-e5-base`, 768 dim, cosine;
- sparse vector: BM25 с IDF в Qdrant;
- payload-фильтры: `section`, `content_type`, `language`, `version`, `path`, `project`;
- гибридный поиск: Qdrant Query API, два prefetch + RRF.

Текущий индекс: **1440 points**, сборка на CPU заняла **353 секунды**.
Поиск после загрузки моделей занимает десятки миллисекунд.

Примеры режимов:

```powershell
# смысловой поиск
uv run docs-rag search --query "How do I use Depends?" --mode dense

# точные идентификаторы
uv run docs-rag search --query "HTTPException" --mode sparse

# гибрид
uv run docs-rag search --query "background tasks" --mode hybrid

# фильтры по метаданным
uv run docs-rag search --query "Depends" --mode hybrid --section tutorial --content-type prose
```

Подробности: [`docs/retrieval.md`](docs/retrieval.md).

## API

| Метод | Путь | Назначение |
|---|---|---|
| `GET` | `/health` | Liveness |
| `GET` | `/ready` | Готовность Qdrant и индекса; `503`, пока points = 0 |
| `GET` | `/api/stats` | Коллекция, число points, версия корпуса, имена векторов |
| `POST` | `/api/search` | Поиск: `dense`, `sparse` или `hybrid` + фильтры |

`/api/search` принимает `query`, `mode`, `top_k`, `section`, `content_type`,
`language`, `version`. Модели загружаются один раз в lifespan; поиск выполняется
в threadpool. Каждый ответ содержит заголовок `X-Request-ID`.

Подробные схемы и примеры: [`docs/api.md`](docs/api.md).

## UI

Streamlit ходит в API по HTTP и не импортирует retrieval-код:

- вкладка «Поиск» — запрос, режим, top-k и фильтры;
- вкладка «Сравнение» — dense / sparse / hybrid side-by-side;
- sidebar проверяет `/ready` и показывает число points.

## Структура

```text
config/ingestion.toml  # корпус, фильтры, чанкинг
src/docs_rag/
├── api/          # FastAPI: routes, schemas, deps, middleware
├── ingestion/    # fetch, parse, includes, chunk, pipeline
├── retrieval/    # embeddings, Qdrant store, indexer, search
├── config.py     # runtime-настройки из .env
├── logging.py    # structlog
└── cli.py        # CLI-точка входа
ui/app.py         # Streamlit: поиск и сравнение режимов
tests/            # unit-, retrieval- и API-тесты
docs/             # архитектура, ingestion, retrieval, API, конфигурация
```

## План этапов

| Этап | Ветка | Статус |
|---|---|---|
| 0 | `chore/stage-0-bootstrap` | смержен |
| 1 | `feat/stage-1-ingestion` | смержен |
| 2 | `feat/stage-2-retrieval` | смержен |
| 3 | `feat/stage-3-api-ui` | текущий: API и Streamlit |
| 4 | `feat/stage-4-generation-rerank` | reranker, DeepSeek, цитаты, SSE, чат |
| 5 | `feat/stage-5-evaluation` | датасет и метрики качества |
| 6 | `chore/stage-6-polish` | Docker UI, HF cache, CI с Qdrant, README, демо |

## Ограничения этапа 3

- Нет reranker: hybrid использует RRF с равными весами.
- Нет генерации ответов, цитат, SSE и чата — это этап 4.
- UI запускается локально через `streamlit run`; в Docker Compose его пока нет.
- Для русского запроса BM25-ветка обычно пустая, работает dense; гибрид корректно падает в dense-only.
- Размер чанка считается приблизительно; точный tokenizer embedding-модели пока не подключён.
- Нет auth и rate limiting.
