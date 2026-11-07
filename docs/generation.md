# Generation

## Pipeline

```text
query
  → retrieval: до RERANK_CANDIDATES результатов
  → cross-encoder rerank
  → top_k источников
  → prompt с нумерованными источниками
  → OpenRouter / DeepSeek stream
  → SSE: sources → token* → done
```

Retrieval остаётся синхронным. API вызывает `SearchService.search` через
`run_in_threadpool`, а LLM-стрим работает асинхронно.

## Reranker

- Модель: `BAAI/bge-reranker-v2-m3` (`RERANK_MODEL`).
- Включается через `RERANK_ENABLED`.
- Device берётся из `EMBEDDING_DEVICE`.
- `RERANK_CANDIDATES` задаёт размер пула до rerank, `RERANK_BATCH_SIZE` и
  `RERANK_MAX_LENGTH` — параметры inference.
- `score` в результате — выход reranker; `retrieval_score` — исходный score.
- CLI: `uv run docs-rag search ... --no-rerank` отключает rerank для запроса.

Первая загрузка модели занимает ~2.1 GiB диска и заметное время; в Docker
HF cache пока не настроен.

## Prompt и цитаты

- В контекст попадают только источники, прошедшие rerank и уложившиеся в
  `LLM_CONTEXT_MAX_TOKENS` (по приблизительным `token_count` чанков).
- Источники нумеруются `[1]...[N]`; эти же номера уходят в SSE-событии `sources`.
- System prompt требует:
  - отвечать только по источникам;
  - не выдумывать API, URL и примеры;
  - цитировать утверждения как `[n]`;
  - отвечать на языке вопроса.
- Если источников нет, LLM не вызывается: возвращается фиксированное сообщение.

## LLM

- `LLM_MODE=openrouter` — OpenRouter chat completions через `httpx` с
  `stream=True`.
- `LLM_MODE=fake` — детерминированные чанки без сети; используется в тестах
  и для локальной проверки UI.
- `LLM_API_KEY` обязателен для OpenRouter. Без ключа `/api/ask` возвращает `503`.
- `LLM_TIMEOUT` ограничивает ожидание ответа; retry нет, чтобы не дублировать
  оплату запросов.
- Ошибки провайдера логируются, клиенту отдаётся общее SSE-событие `error`.

## SSE

Подробная схема событий: [`api.md`](api.md).

- `sources` — всегда первое событие;
- `token` — дельты ответа;
- `done` — модель, число источников, reranked и полное время;
- `error` — ошибка после начала стрима.

Retrieval и rerank выполняются до открытия `StreamingResponse`, поэтому ошибки
поиска возвращаются обычными HTTP-кодами.

## Ограничения

- Чат single-turn: история не передаётся в LLM.
- Нет token usage и стоимости в ответе.
- Нет retry/fallback и стримингового JSON-режима.
- Reranker на CPU может добавлять секунды latency; параметры стоит тюнинговать
  на этапе evaluation.
