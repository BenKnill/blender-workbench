from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any


LEARNING_COVERAGE_SCHEMA = 1
COVERAGE_STATUSES = (
    "implemented",
    "issue_open",
    "needs_exercise",
    "skipped",
    "stale",
)
LINK_KEYS = ("examples", "docs", "issues", "artifacts")


def load_learning_coverage(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _links(row: Mapping[str, Any]) -> Mapping[str, Any]:
    links = row.get("links")
    return links if isinstance(links, Mapping) else {}


def _linked_values(row: Mapping[str, Any], key: str) -> list[Any]:
    values = _links(row).get(key)
    return values if isinstance(values, list) else []


def validate_learning_coverage(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema") != LEARNING_COVERAGE_SCHEMA:
        errors.append(f"schema must be {LEARNING_COVERAGE_SCHEMA}")
    rows = payload.get("rows")
    if not isinstance(rows, list):
        return [*errors, "rows must be a list"]
    seen: set[str] = set()
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, Mapping):
            errors.append(f"row {index} must be an object")
            continue
        row_id = row.get("id")
        if not isinstance(row_id, str) or not row_id:
            errors.append(f"row {index} missing id")
        elif row_id in seen:
            errors.append(f"row {index} duplicate id {row_id!r}")
        else:
            seen.add(row_id)
        if row.get("status") not in COVERAGE_STATUSES:
            errors.append(f"row {row_id or index} has unknown status {row.get('status')!r}")
        for key in ("source_type", "source", "prompt", "lesson"):
            if not isinstance(row.get(key), str) or not row.get(key):
                errors.append(f"row {row_id or index} missing {key}")
        links = row.get("links")
        if not isinstance(links, Mapping):
            errors.append(f"row {row_id or index} missing links object")
            continue
        for key in LINK_KEYS:
            if key in links and not isinstance(links.get(key), list):
                errors.append(f"row {row_id or index} links.{key} must be a list")
    return errors


def uncovered_learning_prompts(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    uncovered = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        if _linked_values(row, "examples") or _linked_values(row, "issues"):
            continue
        uncovered.append(row)
    return uncovered


def coverage_status_counts(payload: Mapping[str, Any]) -> Counter[str]:
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    return Counter(row.get("status") for row in rows if isinstance(row, Mapping))


def _issue_text(values: Iterable[Any]) -> str:
    return ", ".join(f"#{value}" for value in values) or "-"


def _path_text(values: Iterable[Any]) -> str:
    return ", ".join(str(value) for value in values) or "-"


def format_learning_coverage_report(payload: Mapping[str, Any]) -> str:
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    counts = coverage_status_counts(payload)
    lines = ["Learning coverage:", ""]
    for status in COVERAGE_STATUSES:
        lines.append(f"- {status}: {counts.get(status, 0)}")
    lines.extend(["", "Rows:", ""])
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        links = _links(row)
        lines.append(f"- {row.get('id')}: {row.get('status')}")
        lines.append(f"  source: {row.get('source')}")
        lines.append(f"  examples: {_path_text(links.get('examples', []))}")
        lines.append(f"  issues: {_issue_text(links.get('issues', []))}")
    uncovered = uncovered_learning_prompts(payload)
    lines.extend(["", "Uncovered prompts:", ""])
    if not uncovered:
        lines.append("- none")
    else:
        lines.extend(f"- {row.get('id')}: {row.get('prompt')}" for row in uncovered)
    return "\n".join(lines)
