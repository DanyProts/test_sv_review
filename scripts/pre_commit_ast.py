#!/usr/bin/env python3
"""Pre-commit helper that uploads a SystemVerilog file to /analysis/naming."""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from urllib import error, request


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
DEFAULT_NAMING_URL = "http://localhost:8000/analysis/naming/upload"
def get_endpoint_url() -> str:
    """
    Сохраняем обратную совместимость с переменными KIS_AST_*,
    одновременно позволяя переопределять URL через KIS_NAMING_URL.
    """
    return os.getenv("KIS_AST_URL", os.getenv("KIS_NAMING_URL", DEFAULT_NAMING_URL))


def get_timeout() -> float:
    value = os.getenv("KIS_AST_TIMEOUT", os.getenv("KIS_NAMING_TIMEOUT", "30"))
    return float(value)




def should_skip() -> bool:
    return os.getenv("KIS_AST_SKIP") == "1"


def select_sv_file() -> Path | None:
    """
    Возвращает файл, который надо отправить на сервер.

    - Если задана переменная окружения KIS_AST_FILE, используется она.
    - Иначе берём первый .sv файл из папки src.
    """
    env_value = os.getenv("KIS_AST_FILE")
    if env_value:
        candidate = Path(env_value)
        if not candidate.is_absolute():
            candidate = REPO_ROOT / env_value
        if candidate.exists():
            return candidate
        print(f"[pre-commit] Файл из KIS_AST_FILE не найден: {candidate}", file=sys.stderr)
        return None

    sv_files = sorted(SRC_DIR.glob("*.sv"))
    if not sv_files:
        print("[pre-commit] В каталоге src нет файлов .sv — пропускаю отправку.")
        return None
    return sv_files[0]


def _encode_field(boundary: str, name: str, value: str) -> bytes:
    return (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
        f"{value}\r\n"
    ).encode("utf-8")


def _encode_file(boundary: str, field_name: str, file_path: Path, content: bytes) -> bytes:
    filename = file_path.name
    header = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode("utf-8")
    return header + content + b"\r\n"


def build_payload(file_path: Path) -> tuple[bytes, str]:
    """
    Возвращает тело multipart/form-data и его Content-Type.
    """
    boundary = f"kis-pre-commit-{uuid.uuid4().hex}"
    file_bytes = file_path.read_bytes()

    parts = [
        _encode_file(boundary, "file", file_path, file_bytes),
        _encode_field(boundary, "max_depth", "300"),
        _encode_field(boundary, "max_nodes", "20000"),
        _encode_field(boundary, "include_tokens", "false"),
    ]
    closing = f"--{boundary}--\r\n".encode("utf-8")
    body = b"".join(parts) + closing
    content_type = f"multipart/form-data; boundary={boundary}"
    return body, content_type


def send_naming_request(payload: bytes, content_type: str) -> tuple[int, str]:
    url = get_endpoint_url()
    timeout = get_timeout()
    req = request.Request(url, data=payload, headers={"Content-Type": content_type})
    with request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read().decode("utf-8")


def main() -> int:
    if should_skip():
        print("[pre-commit] KIS_AST_SKIP=1, проверка пропущена.")
        return 0

    target_file = select_sv_file()
    if target_file is None:
        # Нечего отправлять — не блокируем коммит.
        return 0

    payload, content_type = build_payload(target_file)

    try:
        status, body = send_naming_request(payload, content_type)
    except error.HTTPError as exc:
        print(f"[pre-commit] Сервер вернул ошибку HTTP {exc.code}:\n{exc.read().decode('utf-8', errors='replace')}")
        return 1
    except error.URLError as exc:
        print(f"[pre-commit] Не удалось подключиться к {get_endpoint_url()}: {exc.reason}")
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"[pre-commit] Непредвиденная ошибка: {exc}")
        return 1

    print(f"[pre-commit] Ответ /analysis/naming/upload (HTTP {status}):\n{body}")
    return 0 if status == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())

