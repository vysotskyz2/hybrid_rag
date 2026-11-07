# План этапа 3: API + Streamlit

> Сохранено: 2026-10-28.
> Контекст: этапы 0–2 смержены. SSE, чат, LLM и reranker перенесены в этап 4.

## 1. Текущее состояние проекта

### Git

- `origin/main` — `5920298`, merge PR #3 (`feat/stage-2-retrieval`).
- Локальный `main` может отставать от `origin/main`.
- Ветка `feat/stage-2-retrieval` чистая и уже влита.
- Следующая ветка: `feat/stage-3-api-ui`.

### Данные и индекс

- 143 документа, 13 служебных файлов пропущено.
- 483 файла из `docs_src` использованы для примеров кода.
- 1440 чанков, 257 028 токенов.
- 1440 points в Qdrant, размерность dense — 768.
- На момент аудита Docker/Qdrant не запущены; данные индекса сохраняются в Docker volume.

### Что уже реализовано

- Ingestion: pinned SHA, скачивание tarball, `docs_src`, include-директивы, фильтры, очистка frontmatter/HTML, структурированный чанкер, CLI, статистика.
- Retrieval: `multilingual-e5-base`, FastEmbed BM25, Qdrant named vectors, IDF, RRF, payload-фильтры, идемпотентная индексация, stale deletion, CLI `index` и `search`.
- Конфигурация: `.env` + `config/ingestion.toml`, CLI-переопределения, `docs/configuration.md`.
- Тесты: 68 кейсов, 1 integration skip.
- Docker: Qdrant + API.
- CI: Ubuntu + Windows, ruff, mypy, pytest.

### Чего не хватает

- API отдаёт только `/health` и `/`; нет `/ready`, `/api/stats`, `/api/search`.
- Нет загрузки моделей/Qdrant в lifespan.
- Нет UI.
- Нет reranker, LLM, цитат, SSE и чата.
- Нет evaluation: датасета, метрик и отчёта.
- CI не запускает Qdrant и integration-тесты.
- Docker API healthcheck имеет `start-period=10s`, меньше cold start моделей.
- Нет UI в Docker Compose и кэша HuggingFace.
- Одна реальная include-директива не резолвится: `../../fastapi/openapi/docs.py` в `how-to/configure-swagger-ui.md`.
- Токены считаются приблизительно; RRF-веса не тюнингованы.

## 2. Решения

1. **SSE и чат — этап 4.** Этап 3 заканчивается на поиске и сравнении режимов.
2. **Sync retrieval + threadpool.** `Retriever` остаётся синхронным, FastAPI вызывает его через `run_in_threadpool`.
3. **Модели загружаются один раз в lifespan.** `/ready` возвращает 503, пока Qdrant/индекс не готовы.
4. **Streamlit ходит в API по HTTP.** UI не импортирует retrieval-код напрямую.
5. **Docker UI — этап 6.** В этапе 3 достаточно локального `streamlit run`.
6. **Один этап — одна ветка.** `main` мержит пользователь; push/merge без просьбы не делать.

## 3. Scope этапа 3

### 3.1 Подготовка

```powershell
git switch main
git pull --ff-only
git switch -c feat/stage-3-api-ui
```

Проверить:

```powershell
docker compose up -d qdrant
Copy-Item .env.example .env
uv sync
```

Если индекс отсутствует или схема менялась:

```powershell
uv run docs-rag ingest
uv run docs-rag index --recreate
```

### 3.2 FastAPI

- [ ] `api/main.py`: app factory + lifespan.
- [ ] В lifespan загрузить `SentenceTransformerDenseEmbedder`, `FastEmbedSparseEmbedder`, `QdrantStore`.
- [ ] `GET /health` — liveness.
- [ ] `GET /ready` — Qdrant доступен, коллекция существует, points > 0; иначе 503.
- [ ] `GET /api/stats` — collection, points, version, vector names.
- [ ] `POST /api/search`:
  - `query`
  - `mode`: `dense` / `sparse` / `hybrid`
  - `top_k`
  - фильтры: `section`, `content_type`, `language`, `version`
- [ ] Вызов sync-retriever через `run_in_threadpool`.
- [ ] Pydantic-схемы запроса/ответа.
- [ ] CORS из `CORS_ORIGINS`.
- [ ] Request ID middleware и latency в логах.
- [ ] Ошибки: 400/422/503 с понятным телом.
- [ ] Не загружать модели при импорте приложения.

Предлагаемая структура:

```text
src/docs_rag/api/
├── main.py
├── routes.py
├── schemas.py
├── deps.py
└── middleware.py
```

### 3.3 Streamlit

- [ ] `ui/app.py`.
- [ ] Вкладка «Поиск»: запрос, режим, top-k, section/content_type, карточки источников.
- [ ] Вкладка «Сравнение»: dense / sparse / hybrid side-by-side.
- [ ] `UI_API_URL` для адреса API.
- [ ] Проверка `/ready` в sidebar.
- [ ] Ошибки API показывать пользователю, а не падать.
- [ ] UI вызывает API через `httpx`, не импортирует retrieval.

Запуск:

```powershell
uv run uvicorn docs_rag.api.main:app --reload
uv run streamlit run ui/app.py
```

### 3.4 Конфигурация

Добавить в `.env.example` и `Settings`:

| Переменная | Назначение |
|---|---|
| `CORS_ORIGINS` | Разрешённые origins для API |
| `UI_API_URL` | URL API для Streamlit |
| `SEARCH_MAX_TOP_K` | Верхняя граница top_k |
| `QUERY_MAX_LENGTH` | Максимальная длина запроса |

### 3.5 Зависимости

Добавить:

```text
streamlit
httpx
```

`httpx` нужен явно для UI/API-клиента; сейчас он присутствует транзитивно.

### 3.6 Тесты

- [ ] API-тесты с fake retriever/store, без скачивания моделей.
- [ ] `/health`, `/ready` success, `/ready` 503.
- [ ] `/api/stats`.
- [ ] `/api/search`: режимы, фильтры, top_k, пустой query, невалидный mode.
- [ ] Проверка CORS/request_id, если реализовано.
- [ ] Опционально integration-тест с реальным Qdrant.
- [ ] Ручной smoke Streamlit.

### 3.7 Документация

- [ ] README: этап 3, API endpoints, запуск UI.
- [ ] `docs/api.md`: запросы/ответы и примеры.
- [ ] Обновить таблицу этапов: SSE/чат — этап 4.
- [ ] `docs/configuration.md`: новые переменные.

## 4. Definition of Done этапа 3

- `uvicorn` и `streamlit run` работают локально.
- Поиск по 1440 points доступен через API.
- UI поиска и сравнения режимов работает.
- Ключ LLM не требуется.
- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy src`
- `uv run pytest -q`
- Ветка `feat/stage-3-api-ui` готова к мержу.
- Нет изменений в `main`; мерж делает пользователь.

## 5. Вне scope этапа 3

- reranker;
- OpenRouter/DeepSeek;
- prompt и цитаты;
- `/api/ask` и SSE;
- чат-вкладка;
- evaluation;
- Docker UI и CI с Qdrant;
- auth, rate limiting, multi-turn, agents.

## 6. Дальнейшие этапы

| Этап | Ветка | Содержимое |
|---|---|---|
| 4 | `feat/stage-4-generation-rerank` | Reranker, DeepSeek, prompt, цитаты, `/api/ask` SSE, чат |
| 5 | `feat/stage-5-evaluation` | 50 вопросов, retrieval/answer метрики, тюнинг RRF/reranker, отчёт |
| 6 | `chore/stage-6-polish` | Docker UI, HF cache, CI+Qdrant, README, демо-GIF, финальный QA |

