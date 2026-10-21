# DocsLens

Гибридный RAG-ассистент по документации FastAPI: BM25 + dense retrieval + cross-encoder reranker.

> Текущий статус: **этап 0 — каркас проекта**. Индексация, поиск и генерация ответов появятся в следующих ветках.

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

## Структура

```text
src/docs_rag/
├── api/          # FastAPI-приложение
├── config.py     # настройки из переменных окружения
├── logging.py    # structlog
└── cli.py        # CLI-точка входа
tests/            # unit- и API-тесты
docs/             # архитектура и проектные решения
```

## План этапов

| Этап | Ветка | Содержимое |
|---|---|---|
| 0 | `chore/stage-0-bootstrap` | каркас, конфиг, инструменты, CI |
| 1 | `feat/stage-1-ingestion` | загрузка и чанкинг документации |
| 2 | `feat/stage-2-retrieval` | Qdrant, dense/sparse/hybrid поиск |
| 3 | `feat/stage-3-api-ui` | API, SSE, Streamlit |
| 4 | `feat/stage-4-generation-rerank` | DeepSeek, цитаты, reranker |
| 5 | `feat/stage-5-evaluation` | датасет и метрики качества |
| 6 | `chore/stage-6-polish` | Docker, README, демо |

## Ограничения этапа 0

- Нет ingestion и поиска.
- Нет вызова LLM.
- API отдаёт только `/health` и информацию о приложении.
- UI ещё не добавлен.
