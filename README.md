# DocsLens

Гибридный RAG-ассистент по документации FastAPI: BM25 + dense retrieval + cross-encoder reranker.

> Текущий статус: **этап 1 — ingestion**. Корпус документации скачивается, парсится и разбивается на чанки. Поиск и генерация ответов появятся в следующих ветках.

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

Собрать корпус документации:

```powershell
uv run docs-rag ingest
```

Результат:

- `data/chunks/chunks.jsonl` — чанки с метаданными;
- `data/chunks/stats.json` — статистика корпуса.

Запустить API:

```powershell
uv run uvicorn docs_rag.api.main:app --reload
```

Swagger: http://127.0.0.1:8000/docs

Qdrant:

```powershell
docker compose up -d qdrant
```

API в Docker:

```powershell
docker compose up --build api
```

## Ingestion

Источник — английская документация FastAPI, зафиксированная на commit
`68cc4cbb2e0600841b0d6bdd1cc29038b54a00e6`.

Pipeline:

1. Скачивает GitHub tarball по pinned SHA.
2. Извлекает только `docs/en/docs/**/*.md`.
3. Убирает служебные страницы, frontmatter, HTML-комментарии и спонсорские блоки.
4. Парсит заголовки и code fences.
5. Режет документ по секциям H1–H6, не разрывая code fences.
6. Сохраняет чанки с URL, заголовком, heading path и типом содержимого.

Текущий корпус:

| Метрика | Значение |
|---|---:|
| Документов | 143 |
| Пропущено служебных файлов | 13 |
| Чанков | 1221 |
| Токенов (приблизительно) | 181 542 |
| Средний чанк | 148.68 |
| Максимальный чанк | 350 |

Отдельные команды:

```powershell
uv run docs-rag fetch
uv run docs-rag chunk
```

## Структура

```text
src/docs_rag/
├── api/          # FastAPI-приложение
├── ingestion/    # fetch, parse, chunk, pipeline
├── config.py     # настройки из переменных окружения
├── logging.py    # structlog
└── cli.py        # CLI-точка входа
tests/            # unit- и API-тесты
docs/             # архитектура, ingestion и проектные решения
```

## План этапов

| Этап | Ветка | Статус |
|---|---|---|
| 0 | `chore/stage-0-bootstrap` | смержен |
| 1 | `feat/stage-1-ingestion` | текущий |
| 2 | `feat/stage-2-retrieval` | Qdrant, dense/sparse/hybrid поиск |
| 3 | `feat/stage-3-api-ui` | API, SSE, Streamlit |
| 4 | `feat/stage-4-generation-rerank` | DeepSeek, цитаты, reranker |
| 5 | `feat/stage-5-evaluation` | датасет и метрики качества |
| 6 | `chore/stage-6-polish` | Docker, README, демо |

## Ограничения этапа 1

- Нет эмбеддингов и загрузки в Qdrant.
- Нет поиска и reranking.
- Нет вызова LLM.
- API отдаёт только `/health` и информацию о приложении.
- UI ещё не добавлен.
- Размер чанка считается приблизительно; точный tokenizer embedding-модели подключится на этапе 2.
