# API Documentation

Документ описывает публичные HTTP-эндпоинты сервиса `kis`. Все ручки доступны после запуска FastAPI-приложения.

```
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

- **Базовый URL:** `http://<host>:8000`
- **Swagger UI:** `GET /docs`
- **Content-Type:** JSON (`application/json`), либо `multipart/form-data` для аплоада файлов
- **Аутентификация:** отсутствует

## Сводная таблица

| Метод | Путь        | Описание                                      |
|-------|-------------|-----------------------------------------------|
| GET   | /health     | Проверка состояния сервиса                    |
| POST  | /example    | Сохранение примера (id + content)             |
| GET   | /example    | Получение последнего сохранённого примера     |
| POST  | /cst        | Построение CST-дерева из текста SystemVerilog |
| POST  | /cst/upload | Построение CST из файла `.sv`                 |
| POST  | /ast        | Построение AST и метаданных из текста         |
| POST  | /ast/upload | Построение AST из загруженного файла `.sv`    |
| POST  | /analysis/naming | Проверка именований в SystemVerilog-фрагменте |

---

## Health

### `GET /health`

Проверка жизнеспособности сервиса.

- **Успех:** `200 OK`
- **Ответ:**
  ```json
  { "status": "ok" }
  ```

---

## Example API

### `POST /example`

Сохраняет пример в in-memory хранилище.

- **Тело запроса (`application/json`, ExampleRequestDTO):**
  ```json
  {
    "id": "123",
    "content": "Hello world!"
  }
  ```
- **Ответ:** `201 Created`, без тела

### `GET /example`

Возвращает последний сохранённый пример.

- **Успех:** `200 OK`
- **Ответ (`ExampleResponseDTO`):**
  ```json
  {
    "id": "123",
    "content": "Hello world!"
  }
  ```
  Если записей нет, поля будут пустыми строками.

---

## CST API (Concrete Syntax Tree)

### `POST /cst`

Строит CST по переданному тексту SystemVerilog.

- **Тело запроса (`CSTRequestDTO`):**
  | Поле           | Тип    | По умолчанию | Описание                                   |
  |----------------|--------|--------------|---------------------------------------------|
  | `verilog_text` | string | —            | Обязательный исходный код SystemVerilog     |
  | `max_depth`    | int    | 300          | Максимальная глубина обхода дерева          |
  | `max_nodes`    | int    | 20000        | Ограничение на количество узлов             |
  | `include_tokens` | bool | false        | Включать текст токена для листовых узлов    |

- **Ответ (`CSTResponseDTO`):**
  ```json
  {
    "root": {
      "kind": "ModuleDeclaration",
      "text": null,
      "children": [
        { "kind": "ModuleHeader", "text": null, "children": [...] }
      ]
    }
  }
  ```

### `POST /cst/upload`

Позволяет отправить `.sv` файл через `multipart/form-data`.

- **Поля формы:**
  | Имя             | Тип                | По умолчанию | Описание                                           |
  |-----------------|--------------------|--------------|-----------------------------------------------------|
  | `file`          | UploadFile (.sv)   | —            | Обязательный файл SystemVerilog                     |
  | `headers_json`  | string (JSON)      | `{}`         | Произвольные заголовки (для аудита, сейчас не используются) |
  | `max_depth`     | int                | 300          |
  | `max_nodes`     | int                | 20000        |
  | `include_tokens`| bool               | false        |

- **Ответ:** идентичен `POST /cst`.

---

## AST API (Unified Abstract Syntax Tree)

### `POST /ast`

Возвращает структурированный AST с модулями, интерфейсами, typedef/struct/enum и связями между инстансами.

- **Тело запроса (`ASTRequestDTO`):**
  | Поле                | Тип    | По умолчанию | Описание                                           |
  |---------------------|--------|--------------|-----------------------------------------------------|
  | `verilog_text`      | string | —            | Обязательный исходный код SystemVerilog             |
  | `include_metadata`  | bool   | true         | Включать агрегированную статистику                  |
  | `include_connections` | bool | true         | Включать связи между инстансами                     |

- **Ответ (`ASTResponseDTO` пример):**
  ```json
  {
    "parser_used": "pyslang_cst",
    "pyverilog_success": false,
    "modules": [
      {
        "name": "top",
        "type": "Module",
        "parameters": [{ "name": "W", "value": "8" }],
        "ports": [
          { "type": "Port", "direction": "input", "name": "clk", "width": "" }
        ],
        "signals": [],
        "nets": [],
        "instances": [
          {
            "type": "child",
            "name": "u_child",
            "connections": [{ "port": "clk", "arg": "clk" }]
          }
        ],
        "always_blocks": [],
        "initial_blocks": [],
        "assigns": [],
        "generate": []
      }
    ],
    "interfaces": [],
    "packages": [],
    "classes": [],
    "typedefs": [],
    "structs": [],
    "enums": [],
    "connections": [
      { "type": "instance", "from_module": "top", "to_module": "child", "instance_name": "u_child" }
    ],
    "metadata": {
      "total_modules": 1,
      "interfaces_count": 0,
      "packages_count": 0,
      "classes_count": 0,
      "typedefs_count": 0
    }
  }
  ```

### `POST /ast/upload`

Файловый вариант запроса.

- **Поля формы:**
  | Имя                  | Тип                | По умолчанию | Описание                                   |
  |----------------------|--------------------|--------------|---------------------------------------------|
  | `file`               | UploadFile (.sv)   | —            | Обязательный файл исходного кода            |
  | `headers_json`       | string (JSON)      | `{}`         | Необязательные пользовательские заголовки   |
  | `include_metadata`   | bool               | true         |
  | `include_connections`| bool               | true         |

- **Ответ:** идентичен `POST /ast`.

---

## Naming Analysis API

### `POST /analysis/naming`

Проверяет SystemVerilog-текст на соответствие правилам именования (модули, экземпляры, порты, тактовые/сбросные сигналы, modport и т.д.).

- **Тело запроса:**
  ```json
  {
    "verilog_text": "module apb2axi_br (...); endmodule",
    "max_depth": 300,
    "max_nodes": 20000,
    "include_tokens": false
  }
  ```
- **Ответ (text/plain):**
  ```
  Обнаружено 2 нарушений (0 критических, 2 предупреждений).

  Нарушения:
  1. [PORT_UPPERCASE] строка 12: Порт 'clk' в модуле 'top' должен быть записан прописными буквами. Рекомендация: Используйте 'CLK'.
  2. [INSTANCE_PREFIX] строка 34: Экземпляр 'child' модуля 'top' должен начинаться с префикса 'u_'. Рекомендация: Переименуйте на 'u_child'.
  ```

- Если нарушений нет, сообщение будет «Нарушений не обнаружено».
- Если построить AST/CST не удалось, список нарушений будет пустым, поэтому рекомендуется сначала убедиться, что дизайн успешно парсится через `/ast` и `/cst`.

### `POST /analysis/naming/upload`

Принимает `multipart/form-data` с файлом `.sv` и теми же параметрами анализа, что и JSON-версия.

- **Поля формы:**
  | Имя             | Тип                | По умолчанию |
  |-----------------|--------------------|--------------|
  | `file`          | UploadFile (.sv)   | —            |
  | `max_depth`     | int                | 300          |
  | `max_nodes`     | int                | 20000        |
  | `include_tokens`| bool               | false        |

- **Ответ:** идентичен `POST /analysis/naming` (text/plain c перечислением строк).

---

## Коды ошибок

| Код | Когда возникает                                |
|-----|------------------------------------------------|
| 400 | Некорректный JSON или невалидные параметры DTO |
| 422 | Ошибка валидации Pydantic (подробнее в ответе) |
| 500 | Внутренняя ошибка при разборе SystemVerilog    |

В ответе FastAPI приходит стандартный JSON с описанием полей, не прошедших проверку.

---

## Примеры запросов

```bash
# Health
curl http://localhost:8000/health

# Сохранение примера
curl -X POST http://localhost:8000/example \
  -H "Content-Type: application/json" \
  -d '{"id":"sample-1","content":"Hello"}'

# AST
curl -X POST http://localhost:8000/ast \
  -H "Content-Type: application/json" \
  -d '{"verilog_text":"module m; endmodule"}'
```

---

## Дополнительно

- Для интерактивного тестирования используйте Swagger UI (`/docs`).
- CLI-утилиты (`python -m src.presentation.cli.cli_module ast|cst`) дублируют функциональность HTTP-ручек в терминале.

