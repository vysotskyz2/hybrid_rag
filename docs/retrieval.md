# Retrieval

## Qdrant collection

Коллекция `fastapi_docs`:

| Компонент | Параметры |
|---|---|
| `dense` | `multilingual-e5-base`, 768 dim, cosine |
| `sparse` | FastEmbed `Qdrant/bm25`, `modifier=IDF` |
| Payload indexes | `section`, `content_type`, `language`, `version`, `path`, `project` |

Имена векторов, distance, коллекция и endpoint задаются в `.env`
(`DENSE_VECTOR_NAME`, `SPARSE_VECTOR_NAME`, `QDRANT_DISTANCE`, `QDRANT_URL`).
При смене схемы нужен `index --recreate`.

Point ID — детерминированный UUID чанка. Payload содержит весь текст чанка и метаданные,
поэтому для выдачи результата не нужен второй запрос.

## Эмбеддинги

Dense:

- документы: `passage: <text>`;
- запросы: `query: <text>`;
- `normalize_embeddings=True`, cosine.

Префиксы и нормализация задаются через `DENSE_QUERY_PREFIX`,
`DENSE_PASSAGE_PREFIX`, `NORMALIZE_EMBEDDINGS`.

Sparse:

- BM25 с английским стеммером (корпус английский);
- Qdrant применяет IDF на своей стороне;
- для русского запроса BM25-ветка обычно пустая, поэтому hybrid корректно
  падает в dense-only.

## Индексация

```powershell
uv run docs-rag index --recreate
```

Что происходит:

1. Загружаются чанки из `data/chunks/chunks.jsonl`.
2. Создаётся коллекция с dense + sparse vectors и payload-индексами.
3. Чанки эмбеддятся батчами по 32 и upsert'ятся в Qdrant.
4. После успешного upsert удаляются stale points той же версии.
5. В конце выводится статистика.

Повторный запуск без `--recreate` обновляет существующие точки по UUID и удаляет
чанки, которых больше нет в JSONL. `--recreate` полностью пересоздаёт коллекцию.

Текущий индекс: **1440 points**. Полная сборка на CPU: **353 секунды**.

## Режимы поиска

| Режим | Что делает | Когда полезен |
|---|---|---|
| `dense` | Только векторный поиск | Перефразы и кросс-язычные RU-запросы |
| `sparse` | Только BM25 | Точные имена: `HTTPException`, `background_tasks` |
| `hybrid` | Dense + sparse prefetch, RRF | Основной режим |

Для `hybrid` каждый retriever отдаёт до `RETRIEVAL_CANDIDATES` кандидатов (по умолчанию 30),
Qdrant объединяет их через RRF.

## CLI

```powershell
uv run docs-rag search --query "How do I use Depends?" --mode hybrid --top-k 5
uv run docs-rag search --query "Как работает внедрение зависимостей?" --mode hybrid
uv run docs-rag search --query "HTTPException" --mode sparse --top-k 3
```

Фильтры:

```powershell
uv run docs-rag search \
  --query "Depends" \
  --mode hybrid \
  --section tutorial \
  --content-type prose \
  --top-k 5
```

Доступные фильтры: `--section`, `--content-type`, `--language`, `--version`.

## Наблюдения

- RU-вопрос «Как работает внедрение зависимостей?» находит `tutorial/dependencies/index.md`
  через dense-ветку.
- Запрос `HTTPException` даёт релевантные чанки через BM25, но первым может идти раздел
  с более высокой частотой термина. Это задача reranker'а на этапе 4.
- Запрос про CORS попадает в `tutorial/cors.md` в top-5, хотя middleware-разделы
  стоят выше. Reranker и тюнинг RRF должны улучшить порядок.
- После загрузки моделей поиск занимает десятки миллисекунд; основная задержка —
  cold start модели.

## Тесты

- Unit-тесты retrieval используют in-memory Qdrant и fake embedders, поэтому не требуют
  скачивания моделей.
- Реальный e5 + BM25 проверяются интеграционным тестом с `RUN_INTEGRATION=1`.
- Полный индекс проверяется вручную командами `index` и `search`.

## Ограничения

- Reranker ещё не подключён.
- Веса RRF не тюнингованы; по умолчанию равные.
- Нет кэша запросов и батчевого поиска.
- Нет API и UI; этап 3.
