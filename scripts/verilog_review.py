#!/usr/bin/env python3
"""
Отправляет изменённые SystemVerilog-файлы на эндпоинт /analysis/naming/upload,
парсит текстовый ответ и печатает GitHub-аннотации и Markdown-отчёт.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import sys
import textwrap
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List, Sequence

import requests


DEFAULT_CONFIG_PATH = ".verilog-review.json"
VIOLATION_RE = re.compile(
    r"""
    ^\s*\d+\.\s*                     # порядковый номер
    \[(?P<rule>[^\]]+)\]\s*          # [RULE]
    строка\s+(?P<line>\d+):\s*       # строка 12:
    (?P<message>.+)$                # текст
    """,
    re.IGNORECASE | re.VERBOSE,
)
FILE_RE = re.compile(r"^Файл:\s*(?P<filename>.+)$", re.IGNORECASE)
SUMMARY_RE = re.compile(
    r"Обнаружено\s+(?P<total>\d+)\s+нарушений\s*\((?P<critical>\d+)\s+критических,\s*(?P<warnings>\d+)\s+предупреждений\)",
    re.IGNORECASE,
)


class ReviewError(Exception):
    """Исключение для ошибок выполнения проверки."""


@dataclass
class RuleInfo:
    severity: str = "warning"
    doc: str | None = None


@dataclass
class Violation:
    file: str
    rule: str
    line: int
    message: str
    severity: str
    doc: str | None


@dataclass
class ReviewResult:
    analyzed_files: list[str]
    violations: list[Violation]
    api_raw_responses: dict[str, str]

    @property
    def stats(self) -> dict[str, int]:
        stats: dict[str, int] = {"error": 0, "warning": 0}
        for v in self.violations:
            stats[v.severity] = stats.get(v.severity, 0) + 1
        return stats


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def build_rule_map(config: dict[str, Any]) -> dict[str, RuleInfo]:
    rule_map: dict[str, RuleInfo] = {}
    for rule_name, meta in config.get("rules", {}).items():
        severity = meta.get("severity", "warning").lower()
        if severity not in {"warning", "error"}:
            severity = "warning"
        rule_map[rule_name] = RuleInfo(severity=severity, doc=meta.get("doc"))
    return rule_map


def should_skip(path: Path, patterns: Sequence[str]) -> bool:
    rel = str(path).replace("\\", "/")
    return any(fnmatch.fnmatch(rel, pattern) for pattern in patterns)


def detect_severity(rule_name: str, rule_map: dict[str, RuleInfo]) -> RuleInfo:
    if rule_name in rule_map:
        return rule_map[rule_name]
    upper = rule_name.upper()
    if "CRIT" in upper or "ERROR" in upper:
        return RuleInfo(severity="error", doc=None)
    return RuleInfo()


def parse_response(text: str, rule_map: dict[str, RuleInfo]) -> tuple[str, list[Violation]]:
    raw_lines = [line.strip() for line in text.splitlines() if line.strip()]
    filename = ""
    violations: list[Violation] = []

    for line in raw_lines:
        file_match = FILE_RE.match(line)
        if file_match:
            filename = file_match.group("filename")
            break

    for line in raw_lines:
        match = VIOLATION_RE.match(line)
        if not match:
            continue
        rule = match.group("rule").strip()
        vline = int(match.group("line"))
        message = match.group("message").strip()
        rule_info = detect_severity(rule, rule_map)
        violations.append(
            Violation(
                file=filename,
                rule=rule,
                line=vline,
                message=message,
                severity=rule_info.severity,
                doc=rule_info.doc,
            )
        )

    return filename, violations


def summarize_header(text: str) -> dict[str, int]:
    for line in text.splitlines():
        line = line.strip()
        match = SUMMARY_RE.search(line)
        if match:
            return {
                "total": int(match.group("total")),
                "critical": int(match.group("critical")),
                "warnings": int(match.group("warnings")),
            }
    return {"total": 0, "critical": 0, "warnings": 0}


def upload_file(
    api_url: str,
    file_path: Path,
    params: dict[str, Any],
    timeout: float,
    retries: int,
) -> str:
    payload = {
        "max_depth": str(params.get("max_depth", 300)),
        "max_nodes": str(params.get("max_nodes", 20000)),
        "include_tokens": str(params.get("include_tokens", False)).lower(),
    }

    for attempt in range(1, retries + 2):
        try:
            with file_path.open("rb") as fh:
                response = requests.post(
                    api_url,
                    files={"file": (file_path.name, fh, "application/octet-stream")},
                    data=payload,
                    timeout=timeout,
                )
            response.raise_for_status()
            return response.text
        except requests.RequestException as exc:  # pragma: no cover - network dependent
            if attempt > retries:
                raise ReviewError(f"Не удалось отправить {file_path}: {exc}") from exc
            sleep_for = min(2**attempt, 10)
            print(f"[verilog-review] Попытка {attempt} провалилась, повтор через {sleep_for}s", file=sys.stderr)
            time.sleep(sleep_for)
    raise ReviewError(f"Не удалось обработать файл {file_path}")


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_report(report_path: Path, data: ReviewResult) -> None:
    ensure_parent(report_path)
    lines: list[str] = []
    lines.append(f"Всего файлов: {len(data.analyzed_files)}")
    stats = data.stats
    lines.append(f"Критических: {stats.get('error', 0)}, предупреждений: {stats.get('warning', 0)}")
    lines.append("")
    for file_name, raw in data.api_raw_responses.items():
        lines.append(f"===== {file_name} =====")
        lines.append(raw.rstrip())
        lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")


def append_summary(summary_path: Path, text: str) -> None:
    ensure_parent(summary_path)
    with summary_path.open("a", encoding="utf-8") as fh:
        fh.write(text + "\n")


def emit_annotations(violations: Iterable[Violation]) -> None:
    for violation in violations:
        gh_format = (
            f"::{ 'error' if violation.severity == 'error' else 'warning' } "
            f"file={violation.file},line={violation.line},title={violation.rule}::"
            f"{violation.message}"
        )
        print(gh_format)


def create_markdown_summary(result: ReviewResult, doc_links: dict[str, str]) -> str:
    stats = result.stats
    lines = [
        f"### Итоги Verilog-review",
        "",
        f"- Файлов проанализировано: **{len(result.analyzed_files)}**",
        f"- Критических нарушений: **{stats.get('error', 0)}**",
        f"- Предупреждений: **{stats.get('warning', 0)}**",
        "",
    ]

    if result.violations:
        lines.append("| Правило | Серьёзность | Документация |")
        lines.append("|---------|-------------|--------------|")
        for violation in result.violations:
            doc = violation.doc or doc_links.get(violation.rule) or doc_links.get("default", "")
            doc_cell = f"[ссылка]({doc})" if doc else ""
            sev = "Critical" if violation.severity == "error" else "Warning"
            lines.append(f"| `{violation.rule}` | {sev} | {doc_cell} |")
        lines.append("")

    default_doc = doc_links.get("overview") or doc_links.get("default")
    if default_doc:
        lines.append(f"Подробнее о правилах: {default_doc}")

    return "\n".join(lines)


def run_review(args: argparse.Namespace) -> ReviewResult:
    config = load_config(Path(args.config))
    rule_map = build_rule_map(config)
    excludes = config.get("exclude", [])
    api_url = args.api_url or config.get("api_url") or os.getenv("VERILOG_REVIEW_API_URL")
    if not api_url:
        raise ReviewError("Не указан URL API (аргумент --api-url или поле api_url/переменная окружения).")

    with Path(args.files_list).open("r", encoding="utf-8") as fh:
        candidates = [Path(line.strip()) for line in fh if line.strip()]

    files = [
        path for path in candidates if path.exists() and not should_skip(path, excludes)
    ]
    if not files:
        return ReviewResult(analyzed_files=[], violations=[], api_raw_responses={})

    violations: list[Violation] = []
    api_raw: dict[str, str] = {}
    analyzed: list[str] = []

    params = {
        "max_depth": config.get("max_depth", 300),
        "max_nodes": config.get("max_nodes", 20000),
        "include_tokens": config.get("include_tokens", False),
    }
    
    # Таймаут: приоритет у конфига, если он задан, иначе используем аргумент (или дефолт 120)
    timeout = config.get("timeout") if "timeout" in config else (args.timeout if args.timeout != 30.0 else 120.0)
    retries = config.get("retries") if "retries" in config else (args.retries if args.retries != 2 else 3)
    
    print(f"[verilog-review] Используется таймаут: {timeout}s, повторов: {retries}", file=sys.stderr)

    for file_path in files:
        response_text = upload_file(
            api_url=api_url,
            file_path=file_path,
            params=params,
            timeout=timeout,
            retries=retries,
        )
        filename, file_violations = parse_response(response_text, rule_map)
        analyzed.append(filename or str(file_path))
        api_raw[filename or str(file_path)] = response_text
        violations.extend(file_violations)

    result = ReviewResult(analyzed_files=analyzed, violations=violations, api_raw_responses=api_raw)

    if args.report_path:
        write_report(Path(args.report_path), result)

    summary_text = create_markdown_summary(result, config.get("documentation", {}))
    if args.summary_path:
        append_summary(Path(args.summary_path), summary_text)

    emit_annotations(result.violations)
    return result


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verilog naming review runner")
    parser.add_argument("--api-url", help="URL эндпоинта /analysis/naming/upload")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="Путь до .verilog-review.json")
    parser.add_argument("--files-list", required=True, help="Файл со списком путей *.sv")
    parser.add_argument("--timeout", type=float, default=30.0, help="Таймаут HTTP-запроса, секунды (по умолчанию из конфига или 120)")
    parser.add_argument("--retries", type=int, default=2, help="Количество повторов при сетевых ошибках")
    parser.add_argument("--report-path", default="artifacts/verilog-review-report.txt", help="Путь полного отчёта")
    parser.add_argument(
        "--summary-path",
        default=os.getenv("GITHUB_STEP_SUMMARY", "artifacts/verilog-review-summary.md"),
        help="Markdown-отчёт (по умолчанию GitHub Step Summary)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        result = run_review(args)
    except ReviewError as exc:
        print(f"[verilog-review] Ошибка: {exc}", file=sys.stderr)
        return 2

    if not result.analyzed_files:
        print("[verilog-review] Нет файлов для анализа.")
        return 0

    has_critical = any(v.severity == "error" for v in result.violations)
    if has_critical:
        print("[verilog-review] Найдены критические нарушения.")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


