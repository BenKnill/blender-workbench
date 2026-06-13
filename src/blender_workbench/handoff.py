from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any


PROMPT_CARD_SCHEMA = 1
HANDOFF_GUIDANCE = "Use this render or study as a structure reference, not final art."
HANDOFF_NOTE_KEYS = (
    "visual_intent",
    "preserve",
    "improve_after",
    "allowed_edits",
    "failure_modes",
    "reference_targets",
)


def _relative_or_absolute(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def _listify(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, Iterable):
        return [str(item) for item in value if str(item)]
    return [str(value)]


def normalize_handoff_notes(notes: Mapping[str, Any] | None = None) -> dict[str, list[str]]:
    values = {key: [] for key in HANDOFF_NOTE_KEYS}
    if not notes:
        return values
    for key in HANDOFF_NOTE_KEYS:
        values[key] = _listify(notes.get(key))
    return values


def _first_note(notes: Mapping[str, Any] | None, key: str) -> str | None:
    values = _listify(notes.get(key) if notes else None)
    return values[0] if values else None


def _source_sweep_metadata(source_sweep_dir: Path | None) -> dict[str, Any]:
    if not source_sweep_dir:
        return {}
    metadata_path = Path(source_sweep_dir) / "metadata.json"
    if not metadata_path.exists():
        return {}
    try:
        payload = json.loads(metadata_path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _pick_handles(metadata: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    workflow = metadata.get("workflow")
    if not isinstance(workflow, Mapping):
        return []
    handles = workflow.get("pick_handles")
    if not isinstance(handles, list):
        return []
    return [handle for handle in handles if isinstance(handle, Mapping)]


def _variant_entries(metadata: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    variants = metadata.get("variants")
    if not isinstance(variants, list):
        return []
    return [variant for variant in variants if isinstance(variant, Mapping)]


def _selected_match(item: Mapping[str, Any], selected: Mapping[str, Any]) -> bool:
    selected_name = selected.get("name")
    selected_label = selected.get("label")
    return item.get("name") == selected_name or bool(selected_label and item.get("label") == selected_label)


def _promotion_command(metadata: Mapping[str, Any], selected: Mapping[str, Any]) -> str | None:
    for handle in _pick_handles(metadata):
        if _selected_match(handle, selected) and isinstance(handle.get("promotion_command"), str):
            return handle["promotion_command"]
    return None


def _rejected_neighbors(metadata: Mapping[str, Any], selected: Mapping[str, Any]) -> list[dict[str, Any]]:
    neighbors: list[dict[str, Any]] = []
    for entry in [*_pick_handles(metadata), *_variant_entries(metadata)]:
        if _selected_match(entry, selected):
            continue
        role = entry.get("role")
        note = entry.get("note")
        tags = entry.get("tags")
        if role in {"failure_anchor", "negative_control", "rejected"} or note:
            neighbors.append(
                {
                    "name": entry.get("name"),
                    "label": entry.get("label"),
                    "role": role,
                    "tags": tags if isinstance(tags, list) else list(tags or ()),
                    "note": note,
                }
            )
    return neighbors


def _artifact_paths(payload: Mapping[str, Any], *, out_dir: Path, root: Path) -> dict[str, str | None]:
    result = payload.get("result") if isinstance(payload.get("result"), Mapping) else {}
    blend_export = payload.get("blend_export") if isinstance(payload.get("blend_export"), Mapping) else {}
    return {
        "readme": _relative_or_absolute(out_dir / "README.md", root),
        "selected_json": _relative_or_absolute(out_dir / "selected.json", root),
        "raw": result.get("raw") if isinstance(result.get("raw"), str) else None,
        "finished": result.get("finished") if isinstance(result.get("finished"), str) else None,
        "blend": blend_export.get("path") if isinstance(blend_export.get("path"), str) else None,
        "open_blend_command": blend_export.get("open_command") if isinstance(blend_export.get("open_command"), str) else None,
    }


def build_handoff_prompt_card(
    *,
    selected_payload: Mapping[str, Any],
    out_dir: Path,
    root: Path,
    title: str = "Selected Render Handoff",
    handoff_notes: Mapping[str, Any] | None = None,
    source_sweep_dir: Path | None = None,
) -> dict[str, Any]:
    selected = selected_payload.get("selected") if isinstance(selected_payload.get("selected"), Mapping) else {}
    source_value = selected_payload.get("source_sweep")
    source_metadata = _source_sweep_metadata(source_sweep_dir)
    notes = normalize_handoff_notes(handoff_notes)
    visual_intent = [*notes["visual_intent"]]
    if isinstance(selected.get("note"), str) and selected["note"]:
        visual_intent.append(selected["note"])
    if not visual_intent and isinstance(source_metadata.get("title"), str):
        visual_intent.append(source_metadata["title"])

    command = _first_note(handoff_notes, "regenerate_command")
    command = command or _promotion_command(source_metadata, selected)
    if not command and isinstance(source_value, str):
        pick = selected.get("name") or selected_payload.get("pick")
        command = f"render_selected_from_sweep(sweep_dir=Path({source_value!r}), pick={pick!r})"

    return {
        "schema_version": PROMPT_CARD_SCHEMA,
        "artifact_type": "handoff_prompt_card",
        "title": title,
        "guidance": HANDOFF_GUIDANCE,
        "selected": {
            "name": selected.get("name"),
            "label": selected.get("label"),
            "role": selected.get("role"),
            "tags": list(selected.get("tags") or ()),
            "settings": selected.get("settings") if isinstance(selected.get("settings"), Mapping) else selected.get("settings"),
        },
        "source": {
            "sweep": source_value,
            "sweep_title": source_metadata.get("title"),
            "source_sweep_fingerprint": selected_payload.get("source_sweep_fingerprint"),
        },
        "artifacts": _artifact_paths(selected_payload, out_dir=out_dir, root=root),
        "reference_targets": notes["reference_targets"],
        "visual_intent": visual_intent,
        "preserve": notes["preserve"],
        "improve_after": notes["improve_after"],
        "allowed_edits": notes["allowed_edits"],
        "failure_modes": notes["failure_modes"],
        "rejected_neighboring_tiles": _rejected_neighbors(source_metadata, selected),
        "regenerate_command": command,
    }


def format_handoff_markdown(card: Mapping[str, Any]) -> str:
    selected = card.get("selected") if isinstance(card.get("selected"), Mapping) else {}
    source = card.get("source") if isinstance(card.get("source"), Mapping) else {}
    artifacts = card.get("artifacts") if isinstance(card.get("artifacts"), Mapping) else {}
    lines = [
        f"# {card.get('title') or 'Selected Render Handoff'}",
        "",
        str(card.get("guidance") or HANDOFF_GUIDANCE),
        "",
        f"Selected variant: `{selected.get('name') or '(unknown)'}`",
    ]
    if selected.get("label"):
        lines.append(f"Label: `{selected['label']}`")
    if selected.get("role"):
        lines.append(f"Role: `{selected['role']}`")
    if selected.get("tags"):
        lines.append(f"Tags: `{', '.join(str(tag) for tag in selected['tags'])}`")
    if source.get("sweep"):
        lines.append(f"Source sweep: `{source['sweep']}`")
    if source.get("sweep_title"):
        lines.append(f"Source title: {source['sweep_title']}")

    for title, key in (
        ("Visual Intent", "visual_intent"),
        ("Preserve", "preserve"),
        ("Improve After Structure Works", "improve_after"),
        ("Allowed Edits", "allowed_edits"),
        ("Known Failure Modes", "failure_modes"),
        ("Reference Targets", "reference_targets"),
    ):
        values = _listify(card.get(key))
        if values:
            lines.extend(["", f"## {title}", ""])
            lines.extend(f"- {value}" for value in values)

    neighbors = card.get("rejected_neighboring_tiles")
    if isinstance(neighbors, list) and neighbors:
        lines.extend(["", "## Rejected Or Risky Neighbor Tiles", ""])
        for item in neighbors:
            if not isinstance(item, Mapping):
                continue
            detail = item.get("note") or item.get("role") or "neighboring tile"
            lines.append(f"- `{item.get('name')}`: {detail}")

    lines.extend(["", "## Files", ""])
    for label, key in (
        ("README", "readme"),
        ("selected.json", "selected_json"),
        ("Raw render", "raw"),
        ("Finished render", "finished"),
        ("Blend export", "blend"),
    ):
        value = artifacts.get(key)
        if value:
            lines.append(f"- {label}: `{value}`")

    if card.get("regenerate_command"):
        lines.extend(["", "## Regenerate", "", "```bash", str(card["regenerate_command"]), "```"])
    lines.append("")
    return "\n".join(lines)


def write_handoff_card(
    *,
    out_dir: Path,
    selected_payload: Mapping[str, Any],
    root: Path,
    title: str = "Selected Render Handoff",
    handoff_notes: Mapping[str, Any] | None = None,
    source_sweep_dir: Path | None = None,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    card = build_handoff_prompt_card(
        selected_payload=selected_payload,
        out_dir=out_dir,
        root=root,
        title=title,
        handoff_notes=handoff_notes,
        source_sweep_dir=source_sweep_dir,
    )
    (out_dir / "prompt_card.json").write_text(json.dumps(card, indent=2) + "\n")
    (out_dir / "handoff.md").write_text(format_handoff_markdown(card))
    return {
        "markdown": _relative_or_absolute(out_dir / "handoff.md", root),
        "prompt_card": _relative_or_absolute(out_dir / "prompt_card.json", root),
        "schema_version": PROMPT_CARD_SCHEMA,
    }


def prompt_card_from_reference_prompt(
    prompt_path: Path,
    *,
    root: Path | None = None,
    reference_targets: Iterable[str] = (),
) -> dict[str, Any]:
    root = root or Path.cwd()
    text = Path(prompt_path).read_text()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    scene = next((line.removeprefix("Scene:").strip() for line in lines if line.startswith("Scene:")), None)
    lighting = next((line.removeprefix("Lighting:").strip() for line in lines if line.startswith("Lighting:")), None)
    preserve = [line for line in lines if line.startswith("Keep ") or line.startswith("Preserve ")]
    improve = [line for line in lines if "Improve " in line or line.startswith("Improve ")]
    return {
        "schema_version": PROMPT_CARD_SCHEMA,
        "artifact_type": "handoff_prompt_card",
        "title": f"{scene or Path(prompt_path).parent.name} Reference Handoff",
        "guidance": HANDOFF_GUIDANCE,
        "selected": {"name": scene, "label": None, "role": "reference_attempt", "tags": ["legacy_reference"]},
        "source": {"reference_prompt": _relative_or_absolute(Path(prompt_path), root), "lighting": lighting},
        "artifacts": {"reference_prompt": _relative_or_absolute(Path(prompt_path), root)},
        "reference_targets": list(reference_targets),
        "visual_intent": [lighting] if lighting else [],
        "preserve": preserve,
        "improve_after": improve,
        "allowed_edits": [],
        "failure_modes": [],
        "rejected_neighboring_tiles": [],
        "regenerate_command": None,
    }
