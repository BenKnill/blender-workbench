from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT_ROOTS = (Path("examples/output"), Path("runs"))


@dataclass(frozen=True)
class PromotionStatus:
    sweep_dir: str
    status: str
    detail: str
    contact_sheet: str | None
    readme: str | None
    selected_json: str | None = None
    pick: str | None = None
    pick_handles: tuple[dict[str, Any], ...] = ()
    promotion_commands: tuple[str, ...] = ()


def _script_args(argv: list[str] | None = None) -> list[str]:
    values = list(sys.argv[1:] if argv is None else argv)
    if "--" in values:
        return values[values.index("--") + 1 :]
    return values


def _relative_or_absolute(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _metadata_is_sweep(payload: dict[str, Any]) -> bool:
    workflow = payload.get("workflow")
    if isinstance(workflow, dict):
        return workflow.get("stage") == "sweep_grid" or workflow.get("next") == "inspect_contact_sheet_pick_variant_render_selected"
    return False


def find_sweep_metadata(output_roots: list[Path], *, root: Path | None = None) -> list[Path]:
    root = (root or Path.cwd()).resolve()
    paths: list[Path] = []
    for output_root in output_roots:
        scan_root = output_root if output_root.is_absolute() else root / output_root
        if not scan_root.exists():
            continue
        for metadata in sorted(scan_root.rglob("metadata.json")):
            try:
                payload = json.loads(metadata.read_text())
            except json.JSONDecodeError:
                continue
            if _metadata_is_sweep(payload):
                paths.append(metadata)
    return paths


def _safe_output_name(value: str) -> str:
    safe = "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in value)
    return safe.strip("_") or "selected"


def _resolve_source_sweep(value: str | None, *, root: Path) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def _source_matches(selected_payload: dict[str, Any], sweep_dir: Path, *, root: Path) -> bool:
    source = _resolve_source_sweep(selected_payload.get("source_sweep"), root=root)
    if source is None:
        workflow = selected_payload.get("workflow")
        if isinstance(workflow, dict):
            source = _resolve_source_sweep(workflow.get("source_sweep"), root=root)
    return source == sweep_dir.resolve()


def _selected_pick(selected_payload: dict[str, Any]) -> str | None:
    selected = selected_payload.get("selected")
    if isinstance(selected, dict) and isinstance(selected.get("name"), str):
        return selected["name"]
    pick = selected_payload.get("pick")
    return pick if isinstance(pick, str) else None


def _load_selected_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _candidate_selected_paths(sweep_dir: Path, handles: list[dict[str, Any]]) -> list[Path]:
    paths: list[Path] = []
    for handle in handles:
        name = handle.get("name")
        if isinstance(name, str):
            paths.append(sweep_dir / "selected" / _safe_output_name(name) / "selected.json")
    paths.extend(sorted((sweep_dir / "selected").glob("*/selected.json")))
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in paths:
        if path not in seen:
            unique.append(path)
            seen.add(path)
    return unique


def _promotion_commands(workflow: dict[str, Any], handles: list[dict[str, Any]]) -> tuple[str, ...]:
    commands = [handle["promotion_command"] for handle in handles if isinstance(handle.get("promotion_command"), str)]
    template = workflow.get("promotion_command_template")
    if isinstance(template, str) and not commands:
        for handle in handles:
            name = handle.get("name")
            index = handle.get("index")
            label = handle.get("label") or name
            if isinstance(name, str):
                try:
                    commands.append(template.format(pick=name, name=name, index=index, label=label))
                except KeyError:
                    continue
    return tuple(commands)


def classify_sweep(metadata_path: Path, *, root: Path | None = None) -> PromotionStatus:
    root = (root or Path.cwd()).resolve()
    sweep_dir = metadata_path.parent.resolve()
    payload = json.loads(metadata_path.read_text())
    workflow = payload.get("workflow") if isinstance(payload.get("workflow"), dict) else {}
    handles = [handle for handle in workflow.get("pick_handles", []) if isinstance(handle, dict)]
    contact_sheet = sweep_dir / "contact_sheet.png"
    readme = sweep_dir / "README.md"
    display_sweep = _relative_or_absolute(sweep_dir, root)
    display_contact = _relative_or_absolute(contact_sheet, root) if contact_sheet.exists() else None
    display_readme = _relative_or_absolute(readme, root) if readme.exists() else None

    if workflow.get("status") in {"rejected_grid", "rejected"}:
        detail = workflow.get("rejection_note") or workflow.get("review_note") or "grid was explicitly rejected"
        return PromotionStatus(
            sweep_dir=display_sweep,
            status="rejected_grid",
            detail=str(detail),
            contact_sheet=display_contact,
            readme=display_readme,
            pick_handles=tuple(handles),
        )

    selected_candidates = _candidate_selected_paths(sweep_dir, handles)
    stale_paths: list[str] = []
    for selected_path in selected_candidates:
        if not selected_path.exists():
            continue
        selected_payload = _load_selected_json(selected_path)
        if not selected_payload:
            stale_paths.append(_relative_or_absolute(selected_path, root))
            continue
        if _source_matches(selected_payload, sweep_dir, root=root):
            return PromotionStatus(
                sweep_dir=display_sweep,
                status="selected_render_complete",
                detail="selected render has matching source_sweep provenance",
                contact_sheet=display_contact,
                readme=display_readme,
                selected_json=_relative_or_absolute(selected_path, root),
                pick=_selected_pick(selected_payload),
                pick_handles=tuple(handles),
            )
        stale_paths.append(_relative_or_absolute(selected_path, root))

    commands = _promotion_commands(workflow, handles)
    if stale_paths:
        return PromotionStatus(
            sweep_dir=display_sweep,
            status="stale_or_ambiguous",
            detail=f"selected output exists but provenance did not match: {', '.join(stale_paths)}",
            contact_sheet=display_contact,
            readme=display_readme,
            pick_handles=tuple(handles),
            promotion_commands=commands,
        )

    if workflow.get("status") == "needs_selected_render" or workflow.get("stage") == "sweep_grid":
        return PromotionStatus(
            sweep_dir=display_sweep,
            status="needs_visual_pick",
            detail="grid has no selected/<pick>/selected.json with matching provenance",
            contact_sheet=display_contact,
            readme=display_readme,
            pick_handles=tuple(handles),
            promotion_commands=commands,
        )

    return PromotionStatus(
        sweep_dir=display_sweep,
        status="stale_or_ambiguous",
        detail="metadata looked like a sweep but had no recognized workflow status",
        contact_sheet=display_contact,
        readme=display_readme,
        pick_handles=tuple(handles),
        promotion_commands=commands,
    )


def promotion_statuses(output_roots: list[Path] | None = None, *, root: Path | None = None) -> list[PromotionStatus]:
    root = (root or Path.cwd()).resolve()
    roots = output_roots or list(DEFAULT_OUTPUT_ROOTS)
    return [classify_sweep(path, root=root) for path in find_sweep_metadata(roots, root=root)]


def format_promotion_report(results: list[PromotionStatus]) -> str:
    lines = ["Sweep promotion status:", ""]
    if not results:
        lines.append("- no sweep metadata found")
        return "\n".join(lines)
    for result in results:
        lines.append(f"- {result.sweep_dir}: {result.status}")
        lines.append(f"  {result.detail}")
        if result.contact_sheet:
            lines.append(f"  contact_sheet: {result.contact_sheet}")
        if result.readme:
            lines.append(f"  readme: {result.readme}")
        if result.selected_json:
            lines.append(f"  selected_json: {result.selected_json}")
        if result.pick:
            lines.append(f"  pick: {result.pick}")
        for handle in result.pick_handles[:8]:
            label = f" ({handle['label']})" if handle.get("label") and handle.get("label") != handle.get("name") else ""
            lines.append(f"  pick_handle: {handle.get('index')}. {handle.get('name')}{label}")
        if len(result.pick_handles) > 8:
            lines.append(f"  pick_handle: ... {len(result.pick_handles)} total")
        for command in result.promotion_commands[:3]:
            lines.append(f"  promote: {command}")
        if len(result.promotion_commands) > 3:
            lines.append(f"  promote: ... {len(result.promotion_commands)} commands total")
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report sweep grids that still need visual picks and selected renders.")
    parser.add_argument("roots", nargs="*", type=Path, help="output roots to scan, default examples/output and runs")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="repository root for relative paths")
    parser.add_argument("--require-promoted", action="store_true", help="exit nonzero if any grid needs a pick or has stale selected output")
    parser.add_argument("--json", action="store_true", help="print machine-readable status JSON")
    return parser.parse_args(_script_args(argv))


def main(argv: list[str] | None = None) -> list[PromotionStatus]:
    args = parse_args(argv)
    results = promotion_statuses(args.roots or None, root=args.root)
    if args.json:
        print(json.dumps([asdict(result) for result in results], indent=2))
    else:
        print(format_promotion_report(results))
    if args.require_promoted and any(result.status in {"needs_visual_pick", "stale_or_ambiguous"} for result in results):
        raise SystemExit(1)
    return results


if __name__ == "__main__":
    main()
