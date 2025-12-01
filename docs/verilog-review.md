## Verilog Naming Review Workflow

Этот документ описывает, как подключить GitHub Actions workflow `verilog-review` и повторно использовать его локально.

### 1. Что делает workflow

- Отслеживает изменения `.sv` файлов **только из папки `src/`**.
- Анализирует **только изменённые** `.sv` файлы из `src/` (для PR — относительно базовой ветки, для push — в последнем коммите).
- Отправляет каждый изменённый файл на API `POST /analysis/naming/upload` (multipart/form-data).
- Собирает ответы от всех файлов в единый отчёт с аннотациями и статистикой.
- Парсит текстовый ответ, создаёт GitHub-аннотации (`::error` / `::warning`) и формирует Markdown-отчёт во вкладке Actions.
- Сохраняет полный текстовый отчёт артефактом `verilog-review-report`.
- Завершает job с ошибкой, если найдены критические нарушения.

### 2. Подготовка секретов и переменных

1. URL API уже настроен в `.verilog-review.json`: `https://termly-terrific-bustard.cloudpub.ru/analysis/naming/upload`
2. При необходимости можно переопределить через секрет `VERILOG_REVIEW_URL` в GitHub (Settings → Secrets → Actions).
3. При желании добавьте дополнительные переменные:
   - `VERILOG_REVIEW_TOKEN` — если требуется авторизация (тогда обновите `scripts/verilog_review.py` для передачи заголовков).
   - `VERILOG_REVIEW_API_URL` — fallback, если не хотите хранить URL в конфиге.

### 3. Конфигурация `.verilog-review.json`

Пример файла уже добавлен в корне репозитория. Основные поля:

- `api_url` — базовый URL (переопределяется секретом).
- `max_depth`, `max_nodes`, `include_tokens` — параметры запроса.
- `exclude` — паттерны файлов/директорий, которые нужно исключать из анализа.
- `rules` — переопределение серьёзности и ссылок на документацию для конкретных правил.
- `documentation` — ссылки, отображаемые в отчёте (overview/default).
- `artifact_name` — имя итогового файла (используется при ручном запуске).

### 4. Локальный запуск

```bash
python scripts/verilog_review.py \
  --files-list sv-files.txt \
  --api-url https://kis.local/analysis/naming/upload \
  --config .verilog-review.json
```

Где `sv-files.txt` — список путей к `.sv` файлам (по одному в строке). Скрипт создаст:

- `artifacts/verilog-review-report.txt` — полный ответ сервиса.
- Markdown-итоги (по умолчанию `artifacts/verilog-review-summary.md`, если переменная `GITHUB_STEP_SUMMARY` не задана).

### 5. GitHub Actions workflow

Файл `.github/workflows/verilog-review.yml` автоматически:

1. Определяет список **изменённых** файлов из папки `src/` (при push — `git diff HEAD~1 HEAD 'src/*.sv'`, при PR — `git diff origin/base...HEAD 'src/*.sv'`).
2. Устанавливает Python 3.11 и кэширует `pip`.
3. Вызывает `scripts/verilog_review.py`, который отправляет каждый файл на API и собирает все ответы воедино.
4. Загружает артефакты `artifacts/` + `sv-files.txt` с полным отчётом по всем проанализированным файлам.

Если файлов нет (например, все изменения попали под `exclude`), job заканчивается успешно.

### 6. Кастомные правила и документация

- Добавьте в `.verilog-review.json` новый ключ `rules.<RULE_NAME>.severity` (`error`/`warning`) и `doc` — ссылка на описание.
- Общие ссылки на гайды разместите в `documentation.overview` или `documentation.default`.
- При отсутствии явного правила серьёзность определяется по названию (`CRITICAL`, `ERROR` → error, иначе warning).

### 7. Исключения и таймауты

- В `exclude` можно использовать шаблоны (`third_party/**`, `vendor/**` и т.д.).
- Таймаут и число повторов настраиваются опциями `--timeout` и `--retries` (значения по умолчанию: 30 секунд и 2 повтора).
- При сетевых ошибках скрипт сделает экспоненциальный повтор перед тем, как завершиться с ошибкой.

### 8. Интеграция с GitHub Security (опционально)

- Текущий workflow создаёт только аннотации и артефакт.
- Для публикации в Security tab можно дополнительно конвертировать отчёт в SARIF и использовать `github/codeql-action/upload-sarif`.
- Базовая структура результатов (`scripts/verilog_review.py`) позволяет добавить экспорт в SARIF без изменения workflow.

### 9. Полезные файлы

- `.github/workflows/verilog-review.yml` — основной pipeline.
- `scripts/verilog_review.py` — клиент API и парсер ответов.
- `.verilog-review.json` — конфигурация правил.

При необходимости копируйте эти файлы в другие репозитории, обновляя URL, секреты и список правил.

