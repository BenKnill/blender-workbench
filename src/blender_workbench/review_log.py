from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REVIEW_SCHEMA_VERSION = 1
REVIEW_ACTIONS = (
    "render_selected",
    "rerun_wider_stride",
    "rerun_narrower_stride",
    "change_axis",
    "reject_grid",
)
README_START = "<!-- visual-review:start -->"
README_END = "<!-- visual-review:end -->"


def _relative_or_absolute(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _load_metadata(sweep_dir: Path) -> dict[str, Any]:
    metadata_path = Path(sweep_dir) / "metadata.json"
    if not metadata_path.exists():
        raise FileNotFoundError(metadata_path)
    metadata = json.loads(metadata_path.read_text())
    if not isinstance(metadata.get("variants"), list):
        raise ValueError(f"{metadata_path} does not contain a variants list")
    return metadata


def _variant_names(metadata: Mapping[str, Any]) -> set[str]:
    names: set[str] = set()
    for item in metadata.get("variants", []):
        if isinstance(item, Mapping) and isinstance(item.get("name"), str):
            names.add(item["name"])
    return names


def _pick_commands(metadata: Mapping[str, Any]) -> dict[str, str]:
    workflow = metadata.get("workflow")
    handles = workflow.get("pick_handles", []) if isinstance(workflow, Mapping) else []
    commands: dict[str, str] = {}
    for handle in handles:
        if not isinstance(handle, Mapping):
            continue
        name = handle.get("name")
        command = handle.get("promotion_command")
        if isinstance(name, str) and isinstance(command, str):
            commands[name] = command
    return commands


def _name_list(values: Iterable[str] | None) -> list[str]:
    if not values:
        return []
    return list(dict.fromkeys(str(value) for value in values if str(value)))


def _reject_list(rejects: Mapping[str, str] | Iterable[tuple[str, str]] | None) -> list[dict[str, str]]:
    if not rejects:
        return []
    items = rejects.items() if isinstance(rejects, Mapping) else rejects
    return [{"name": str(name), "reason": str(reason)} for name, reason in items if str(name)]


def _validate_names(names: Iterable[str], valid_names: set[str], field: str) -> None:
    missing = [name for name in names if name not in valid_names]
    if missing:
        preview = ", ".join(sorted(valid_names)[:8])
        raise ValueError(f"{field} contains unknown variant(s): {', '.join(missing)}. Available names: {preview}")


def _entry(entries: dict[str, dict[str, Any]], name: str, decision: str, *, note: str | None = None, tags: Iterable[str] = ()) -> None:
    item = entries.setdefault(name, {"name": name, "decisions": [], "tags": []})
    if decision not in item["decisions"]:
        item["decisions"].append(decision)
    for tag in tags:
        if tag and tag not in item["tags"]:
            item["tags"].append(tag)
    if note:
        item["note"] = note


def build_review_payload(
    *,
    sweep_dir: Path,
    metadata: Mapping[str, Any],
    winner: str | None = None,
    promising: Iterable[str] = (),
    rejects: Mapping[str, str] | Iterable[tuple[str, str]] | None = None,
    failure_anchors: Iterable[str] = (),
    tags_by_tile: Mapping[str, Iterable[str]] | None = None,
    next_action: str | None = None,
    next_note: str | None = None,
    reviewer: str = "codex",
    tool: str = "tools/review_sweep.py",
    reviewed_at: str | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    valid_names = _variant_names(metadata)
    if not valid_names:
        raise ValueError("metadata has no named variants to review")
    root = root or Path.cwd()
    sweep_dir = Path(sweep_dir)
    promising_names = _name_list(promising)
    reject_items = _reject_list(rejects)
    failure_names = _name_list(failure_anchors)
    all_names = ([winner] if winner else []) + promising_names + [item["name"] for item in reject_items] + failure_names
    _validate_names([name for name in all_names if name], valid_names, "review")

    action = next_action or ("render_selected" if winner else "reject_grid")
    if action not in REVIEW_ACTIONS:
        raise ValueError(f"Unknown review next_action {action!r}; expected one of: {', '.join(REVIEW_ACTIONS)}")
    if action == "render_selected" and not winner:
        raise ValueError("next_action='render_selected' requires a winner")

    commands = _pick_commands(metadata)
    entries: dict[str, dict[str, Any]] = {}
    if winner:
        _entry(entries, winner, "winner", tags=("winner", "promising"))
    for name in promising_names:
        _entry(entries, name, "promising", tags=("promising",))
    for item in reject_items:
        _entry(entries, item["name"], "reject", note=item.get("reason"), tags=("reject",))
    for name in failure_names:
        _entry(entries, name, "failure_anchor", tags=("good_failure_anchor",))
    for name, tags in (tags_by_tile or {}).items():
        _validate_names([name], valid_names, "tags_by_tile")
        _entry(entries, name, "tagged", tags=tags)

    reviewed = list(dict.fromkeys(all_names))
    payload: dict[str, Any] = {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "reviewer": reviewer,
        "tool": tool,
        "reviewed_at": reviewed_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_sweep": _relative_or_absolute(sweep_dir, root),
        "contact_sheet": _relative_or_absolute(sweep_dir / "contact_sheet.png", root),
        "winner": winner,
        "promotion_pick": winner,
        "promotion_command": commands.get(winner) if winner else None,
        "picks": [winner] if winner else [],
        "promising": promising_names,
        "rejects": reject_items,
        "failure_anchors": failure_names,
        "reviewed": reviewed,
        "entries": list(entries.values()),
        "next_action": action,
        "next_note": next_note,
    }
    return payload


def review_summary(review: Mapping[str, Any]) -> list[str]:
    lines: list[str] = []
    winner = review.get("winner")
    if winner:
        lines.append(f"Winner: `{winner}`")
    else:
        lines.append("Winner: none recorded")
    promising = review.get("promising")
    if isinstance(promising, list) and promising:
        lines.append("Promising alternates: " + ", ".join(f"`{name}`" for name in promising))
    rejects = review.get("rejects")
    if isinstance(rejects, list) and rejects:
        lines.append("Rejected tiles:")
        for item in rejects:
            if isinstance(item, Mapping):
                reason = f" - {item.get('reason')}" if item.get("reason") else ""
                lines.append(f"- `{item.get('name')}`{reason}")
    anchors = review.get("failure_anchors")
    if isinstance(anchors, list) and anchors:
        lines.append("Failure anchors: " + ", ".join(f"`{name}`" for name in anchors))
    action = review.get("next_action") or "unknown"
    lines.append(f"Next action: `{action}`")
    if review.get("next_note"):
        lines.append(f"Next note: {review['next_note']}")
    if review.get("promotion_command"):
        lines.extend(["Promotion command:", "```bash", str(review["promotion_command"]), "```"])
    return lines


def update_review_readme(sweep_dir: Path, review: Mapping[str, Any]) -> Path:
    sweep_dir = Path(sweep_dir)
    readme_path = sweep_dir / "README.md"
    existing = readme_path.read_text() if readme_path.exists() else f"# {sweep_dir.name}\n"
    section = "\n".join([README_START, "## Visual Review", "", *review_summary(review), README_END, ""])
    if README_START in existing and README_END in existing:
        before, rest = existing.split(README_START, 1)
        _, after = rest.split(README_END, 1)
        text = before.rstrip() + "\n\n" + section + after.lstrip()
    else:
        text = existing.rstrip() + "\n\n" + section
    readme_path.write_text(text)
    return readme_path


def write_review_log(
    sweep_dir: Path,
    *,
    winner: str | None = None,
    promising: Iterable[str] = (),
    rejects: Mapping[str, str] | Iterable[tuple[str, str]] | None = None,
    failure_anchors: Iterable[str] = (),
    tags_by_tile: Mapping[str, Iterable[str]] | None = None,
    next_action: str | None = None,
    next_note: str | None = None,
    reviewer: str = "codex",
    tool: str = "tools/review_sweep.py",
    reviewed_at: str | None = None,
    root: Path | None = None,
) -> Path:
    sweep_dir = Path(sweep_dir)
    metadata = _load_metadata(sweep_dir)
    review = build_review_payload(
        sweep_dir=sweep_dir,
        metadata=metadata,
        winner=winner,
        promising=promising,
        rejects=rejects,
        failure_anchors=failure_anchors,
        tags_by_tile=tags_by_tile,
        next_action=next_action,
        next_note=next_note,
        reviewer=reviewer,
        tool=tool,
        reviewed_at=reviewed_at,
        root=root,
    )
    path = sweep_dir / "review.json"
    path.write_text(json.dumps(review, indent=2))
    update_review_readme(sweep_dir, review)
    try:
        from .review_page import write_review_page

        write_review_page(sweep_dir, root=root or Path.cwd())
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return path


def load_review_log(sweep_dir: Path) -> dict[str, Any] | None:
    path = Path(sweep_dir) / "review.json"
    if not path.exists():
        return None
    payload = json.loads(path.read_text())
    return payload if isinstance(payload, dict) else None


def selected_pick_from_review(sweep_dir: Path) -> str | None:
    review = load_review_log(sweep_dir)
    if not review:
        return None
    if review.get("next_action") not in (None, "render_selected"):
        return None
    pick = review.get("promotion_pick") or review.get("winner")
    return pick if isinstance(pick, str) and pick else None
