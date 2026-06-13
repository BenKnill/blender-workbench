from __future__ import annotations

import json
import glob
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


def linked_issue_numbers(payload: Mapping[str, Any]) -> tuple[int, ...]:
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    issues: list[int] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        for value in _linked_values(row, "issues"):
            try:
                issues.append(int(value))
            except (TypeError, ValueError):
                continue
    return tuple(sorted(set(issues)))


def _link_exists(value: Any, *, root: Path) -> bool:
    if not isinstance(value, str) or not value:
        return False
    path = root / value
    if any(char in value for char in "*?["):
        return bool(glob.glob(str(path)))
    return path.exists()


def audit_learning_coverage(
    payload: Mapping[str, Any],
    *,
    root: Path | None = None,
    check_paths: bool = True,
    issue_states: Mapping[int, str | None] | None = None,
) -> list[dict[str, Any]]:
    root = root or Path.cwd()
    issue_states = issue_states or {}
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    findings: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        row_id = str(row.get("id") or "<unknown>")
        status = row.get("status")
        links = _links(row)
        if issue_states:
            issue_values = []
            for value in links.get("issues", []):
                try:
                    issue_values.append(int(value))
                except (TypeError, ValueError):
                    findings.append(
                        {
                            "row_id": row_id,
                            "code": "invalid_issue_link",
                            "severity": "stale",
                            "message": f"linked issue value {value!r} is not an integer",
                        }
                    )
            states = {issue: issue_states.get(issue) for issue in issue_values}
            missing = [issue for issue, state in states.items() if state is None]
            if missing:
                findings.append(
                    {
                        "row_id": row_id,
                        "code": "issue_lookup_missing",
                        "severity": "stale",
                        "message": f"linked issue state unavailable for {', '.join(f'#{issue}' for issue in missing)}",
                    }
                )
            known_states = [str(state).lower() for state in states.values() if state is not None]
            if status == "issue_open" and known_states and all(state == "closed" for state in known_states):
                example_count = len([value for value in links.get("examples", []) if value])
                suggestion = "implemented" if example_count else "stale"
                findings.append(
                    {
                        "row_id": row_id,
                        "code": "issue_open_all_issues_closed",
                        "severity": "stale",
                        "message": (
                            f"status is issue_open but all linked issues are closed: "
                            f"{', '.join(f'#{issue}' for issue in sorted(states))}"
                        ),
                        "suggestion": suggestion,
                    }
                )
        if check_paths and status == "implemented":
            for key in ("examples", "docs", "artifacts"):
                missing = [str(value) for value in links.get(key, []) if not _link_exists(value, root=root)]
                if missing:
                    findings.append(
                        {
                            "row_id": row_id,
                            "code": "implemented_missing_path",
                            "severity": "stale",
                            "message": f"implemented row has missing linked {key}: {', '.join(missing)}",
                        }
                    )
    return findings


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


def format_learning_coverage_audit(findings: Iterable[Mapping[str, Any]]) -> str:
    finding_list = list(findings)
    lines = ["Learning coverage freshness audit:", ""]
    if not finding_list:
        lines.append("- no freshness findings")
        return "\n".join(lines)
    for finding in finding_list:
        suggestion = f"; suggested status: {finding['suggestion']}" if finding.get("suggestion") else ""
        lines.append(f"- {finding.get('row_id')}: {finding.get('code')}{suggestion}")
        lines.append(f"  {finding.get('message')}")
    return "\n".join(lines)
