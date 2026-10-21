# Ingestion

## Источник

- Репозиторий: `fastapi/fastapi`
- Commit: `68cc4cbb2e0600841b0d6bdd1cc29038b54a00e6`
- Путь: `docs/en/docs`
- Сайт для цитат: `https://fastapi.tiangolo.com`

SHA фиксируется в `DOCS_REF`, поэтому корпус воспроизводим. При обновлении документации
нужно осознанно поменять `DOCS_REF` и пересобрать чанки.

## Фильтрация

Исключаются:

- `release-notes.md` — 725 KB релизных заметок, которые зашумляют retrieval;
- служебные страницы (`about`, `learn`, `resources`, `contributing`, `help-fastapi`,
  `translation-banner`, `translations`, `management`, `newsletter`, `fastapi-people`,
  `external-links`);
- файлы, начинающиеся с `_`;
- изображения, CSS и JS.

Дополнительно:

- YAML frontmatter удаляется;
- HTML-комментарии и HTML-теги вне code fences удаляются;
- секции со словом `Sponsor` в heading path пропускаются.

## Парсинг и чанкинг

- Заголовки H1–H6 задают структуру и heading path.
- Строки внутри code fences не считаются заголовками.
- Markdown-анкоры вида `{ #anchor }` удаляются из заголовков.
- Code fences сохраняются целиком; слишком длинный code block делится с повторным
  открытием и закрытием fence.
- Длинные секции делятся по блокам, затем по словам, с overlap.
- Размер считается приблизительным token counter'ом: слова и знаки пунктуации.
  Параметры: target 280, max 350, overlap 50.
- URL строится из пути: `tutorial/body.md` → `https://fastapi.tiangolo.com/tutorial/body/`.

## Метаданные чанка

| Поле | Описание |
|---|---|
| `chunk_id` | Детерминированный UUID от project/version/path/index |
| `doc_id`, `path` | Относительный путь Markdown-файла |
| `url` | Ссылка на раздел документации |
| `title` | H1 документа или имя файла |
| `heading_path` | Путь заголовков, например `Tutorial > Dependencies > Depends` |
| `section` | Верхний раздел: `tutorial`, `advanced`, `reference`, ... |
| `content_type` | `prose`, `code` или `mixed` |
| `language`, `project`, `version` | Язык, проект и pinned commit |
| `chunk_index` | Порядковый номер чанка в документе |
| `content_hash` | SHA-256 текста чанка |
| `token_count` | Приблизительное число токенов |

## Команды

```powershell
uv run docs-rag ingest
uv run docs-rag fetch
uv run docs-rag chunk
```

`ingest` выполняет fetch и chunk. Повторный запуск использует кэш архива и
извлечённых документов; `--force` перекачивает архив и пересобирает исходники.

## Текущая статистика

```json
{
  "files": 143,
  "skipped": 13,
  "chunks": 1221,
  "tokens": 181542,
  "avg_tokens": 148.68,
  "min_tokens": 10,
  "max_tokens": 350,
  "content_types": {
    "code": 42,
    "mixed": 218,
    "prose": 961
  },
  "sections": {
    "advanced": 272,
    "deployment": 132,
    "how-to": 80,
    "reference": 36,
    "root": 148,
    "tutorial": 553
  }
}
```

Статистика пересобирается командой `uv run docs-rag ingest` и сохраняется в
`data/chunks/stats.json`.
