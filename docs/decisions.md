# Проектные решения

| Область | Решение | Причина |
|---|---|---|
| Корпус | Английские доки FastAPI, pinned commit | Официальный источник с точными API-именами; версия воспроизводима |
| Язык запросов | RU и EN | Dense-модель мультиязычная, BM25 помогает с английскими идентификаторами |
| Чанкинг | По заголовкам, 350–450 токенов, overlap ~15% | Сохраняет смысл секции и не рвёт code fences |
| Dense | `intfloat/multilingual-e5-base` | Хороший баланс качества и CPU- latency |
| Sparse | FastEmbed `Qdrant/bm25`, `language=english` | Точные термины и редкие идентификаторы |
| Vector DB | Qdrant 1.19 | Нативный hybrid search, sparse vectors, payload-фильтры |
| Fusion | RRF | Не требует сравнения несопоставимых score |
| Reranker | `BAAI/bge-reranker-v2-m3` | Мультиязычный cross-encoder, работает на CPU |
| LLM | OpenRouter + DeepSeek | Дешёвый доступ к разным моделям через OpenAI-compatible API |
| Тесты LLM | `FakeLLM` | Детерминированные тесты без ключа, сети и затрат |
| API | FastAPI + SSE | OpenAPI из коробки и стриминг ответа |
| UI | Streamlit поверх API | Быстрое демо без frontend-сборки |
| Оркестрация | Собственный код без LangChain | Прозрачный пайплайн и контроль над каждым этапом |
| Инфраструктура | uv, Docker Compose, GitHub Actions | Воспроизводимость и автоматические проверки |
