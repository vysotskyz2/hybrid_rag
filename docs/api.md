# API

FastAPI-приложение живёт в `src/docs_rag/api/`. Swagger доступен по `/docs`,
OpenAPI — по `/openapi.json`.

```powershell
uv run uvicorn docs_rag.api.main:app --reload
```

Модели и `QdrantStore` загружаются один раз в lifespan. При импорте приложения
модели не скачиваются. Sync-`Retriever` вызывается через `run_in_threadpool`,
поэтому event loop не блокируется.

## Endpoints

| Метод | Путь | Назначение |
|---|---|---|
| `GET` | `/health` | Liveness, не проверяет Qdrant |
| `GET` | `/ready` | Qdrant доступен, коллекция существует, `points > 0` |
| `GET` | `/api/stats` | Коллекция, points, версия корпуса, имена векторов |
| `POST` | `/api/search` | Поиск по индексу |

Все ответы содержат заголовок `X-Request-ID`. Если клиент передал его в запросе,
значение возвращается без изменений; иначе генерируется UUID.

## GET /health

```json
{"status": "ok"}
```

## GET /ready

Готовность индекса:

```json
{
  "status": "ready",
  "collection": "fastapi_docs",
  "points": 1440
}
```

Если Qdrant недоступен, коллекция отсутствует или пуста — `503`:

```json
{
  "detail": "Index is not ready",
  "reason": "Collection is empty"
}
```

## GET /api/stats

```json
{
  "collection": "fastapi_docs",
  "points": 1440,
  "version": "68cc4cbb2e0600841b0d6bdd1cc29038b54a00e6",
  "vectors": ["dense", "sparse"]
}
```

`version` — версия корпуса из payload проиндексированных чанков (pinned commit).
Если Qdrant недоступен, возвращается `503`.

## POST /api/search

Тело запроса:

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `query` | string | да | Запрос; пробелы обрезаются, пустой запрещён |
| `mode` | `dense` / `sparse` / `hybrid` | нет | По умолчанию `RETRIEVAL_DEFAULT_MODE` |
| `top_k` | int ≥ 1 | нет | По умолчанию `RETRIEVAL_TOP_K`, максимум `SEARCH_MAX_TOP_K` |
| `section` | string | нет | Например, `tutorial` |
| `content_type` | `prose` / `code` / `mixed` | нет | Тип чанка |
| `language` | string | нет | Например, `en` |
| `version` | string | нет | Версия корпуса |

Пример:

```powershell
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

Ответ:

```json
{
  "query": "How do I use Depends?",
  "mode": "hybrid",
  "top_k": 3,
  "results": [
    {
      "chunk_id": "c0a8017e-...",
      "score": 0.6667,
      "path": "tutorial/dependencies/index.md",
      "url": "https://fastapi.tiangolo.com/tutorial/dependencies/",
      "title": "Dependencies",
      "heading_path": "Dependencies > First Steps > ...",
      "section": "tutorial",
      "content_type": "prose",
      "language": "en",
      "version": "68cc4cbb2e0600841b0d6bdd1cc29038b54a00e6",
      "token_count": 180,
      "text": "..."
    }
  ]
}
```

`results` отсортированы по убыванию score. Для `hybrid` score — результат RRF,
поэтому его нельзя напрямую сравнивать со score dense или sparse.

## Ошибки

| Код | Когда |
|---|---|
| `400` | `query` длиннее `QUERY_MAX_LENGTH`, `top_k > SEARCH_MAX_TOP_K`, ошибка валидации retriever |
| `422` | Пустой `query`, невалидный `mode`/`content_type`, `top_k < 1`, неверный JSON |
| `503` | Qdrant/индекс недоступен, `/ready` не готов, ошибка backend |

Тело ошибки:

```json
{"detail": "top_k must not exceed 20"}
```

Для `/ready` дополнительно приходит `reason`.

## CORS

Разрешённые origins задаются в `CORS_ORIGINS` (JSON-массив). По умолчанию
разрешён `http://localhost:8501` — адрес Streamlit. CORS нужен только браузерным
клиентам; Streamlit обращается к API с сервера через `httpx`.
