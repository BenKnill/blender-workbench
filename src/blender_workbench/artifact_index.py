from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ARTIFACT_INDEX_SCHEMA = 1
ARTIFACT_TYPES = (
    "sweep",
    "selected_render",
    "legacy_gallery",
    "reference_study",
    "fixture",
    "postprocess_sweep",
)
ARTIFACT_STATUSES = (
    "exploratory",
    "needs_visual_pick",
    "promising",
    "rejected",
    "promoted",
    "stale",
    "unknown",
)


@dataclass(frozen=True)
class ArtifactDescriptor:
    id: str
    artifact_type: str
    status: str
    root: str
    metadata: str | None = None
    preview: str | None = None
    source_cue: str | None = None
    render_profile: str | None = None
    selected_variant: str | None = None
    pick_handles: tuple[str, ...] = ()
    raw_paths: tuple[str, ...] = ()
    finished_paths: tuple[str, ...] = ()
    learning_coverage: tuple[str, ...] = ()
    compatibility_notes: tuple[str, ...] = ()


def _relative_or_absolute(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def _resolve_metadata_path(value: str, *, artifact_dir: Path, root: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    candidates = (root / path, artifact_dir / path, artifact_dir.parent / path)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return root / path


def _path_from_metadata(value: str | None, *, artifact_dir: Path, root: Path) -> str | None:
    if not value:
        return None
    return _relative_or_absolute(_resolve_metadata_path(value, artifact_dir=artifact_dir, root=root), root)


def _first_existing(paths: Iterable[str | None], *, artifact_dir: Path, root: Path) -> str | None:
    for value in paths:
        if not value:
            continue
        path = _resolve_metadata_path(value, artifact_dir=artifact_dir, root=root)
        if path.exists():
            return _relative_or_absolute(path, root)
    return None


def _fallback_preview(artifact_dir: Path, root: Path) -> str | None:
    for name in ("contact_sheet.png", "review.html"):
        path = artifact_dir / name
        if path.exists():
            return _relative_or_absolute(path, root)
    for pattern in ("*.finished.png", "*.png", "*.jpg", "*.jpeg"):
        matches = sorted(artifact_dir.glob(pattern))
        if matches:
            return _relative_or_absolute(matches[0], root)
    return None


def _metadata_artifact_id(metadata_path: Path, root: Path) -> str:
    try:
        rel = str(metadata_path.parent.resolve().relative_to(root.resolve()))
    except ValueError:
        try:
            rel = str(Path("external") / metadata_path.parent.resolve().relative_to(root.resolve().parent))
        except ValueError:
            rel = str(Path("external") / metadata_path.parent.name)
    return rel.replace("/", ":").replace("..", "up") or metadata_path.parent.name


def _status_from_workflow(workflow: Mapping[str, Any]) -> str:
    status = workflow.get("status")
    if status == "needs_selected_render":
        return "needs_visual_pick"
    if status in {"rejected_grid", "rejected"}:
        return "rejected"
    if status == "complete":
        return "promoted"
    return "exploratory"


def _pick_handles(workflow: Mapping[str, Any]) -> tuple[str, ...]:
    handles = workflow.get("pick_handles")
    if not isinstance(handles, list):
        return ()
    names = [handle.get("name") for handle in handles if isinstance(handle, Mapping)]
    return tuple(name for name in names if isinstance(name, str))


def _mapping_items(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _metadata_values(items: Iterable[Mapping[str, Any]], key: str) -> list[str | None]:
    return [item.get(key) for item in items if isinstance(item.get(key), str)]


def _metadata_names(items: Iterable[Mapping[str, Any]]) -> tuple[str, ...]:
    return tuple(item["name"] for item in items if isinstance(item.get("name"), str))


def _resolved_metadata_paths(
    items: Iterable[Mapping[str, Any]],
    key: str,
    *,
    artifact_dir: Path,
    root: Path,
) -> tuple[str, ...]:
    return tuple(
        path
        for path in (
            _path_from_metadata(item.get(key), artifact_dir=artifact_dir, root=root)
            for item in items
            if isinstance(item.get(key), str)
        )
        if path
    )


def _coverage_refs(payload: Mapping[str, Any]) -> tuple[str, ...]:
    for key in ("learning_coverage", "coverage", "coverage_refs"):
        value = payload.get(key)
        if isinstance(value, str):
            return (value,)
        if isinstance(value, list):
            return tuple(str(item) for item in value if str(item))
    return ()


def _render_config_profile(payload: Mapping[str, Any]) -> str | None:
    config = payload.get("render_config")
    if isinstance(config, Mapping):
        engine = config.get("engine")
        samples = config.get("samples")
        if engine or samples is not None:
            return f"{engine or 'unknown'}:{samples if samples is not None else 'unknown'}"
    return None


def _from_workbench_sweep(metadata_path: Path, payload: Mapping[str, Any], root: Path) -> ArtifactDescriptor:
    artifact_dir = metadata_path.parent
    workflow = payload.get("workflow") if isinstance(payload.get("workflow"), Mapping) else {}
    variants = _mapping_items(payload.get("variants"))
    preview = _first_existing(
        [
            "contact_sheet.png",
            *_metadata_values(variants, "finished"),
            *_metadata_values(variants, "raw"),
        ],
        artifact_dir=artifact_dir,
        root=root,
    )
    return ArtifactDescriptor(
        id=_metadata_artifact_id(metadata_path, root),
        artifact_type="sweep",
        status=_status_from_workflow(workflow),
        root=_relative_or_absolute(artifact_dir, root),
        metadata=_relative_or_absolute(metadata_path, root),
        preview=preview,
        source_cue=str(payload.get("title") or workflow.get("required_decision") or "workbench sweep"),
        render_profile=_render_config_profile(payload),
        pick_handles=_pick_handles(workflow),
        raw_paths=_resolved_metadata_paths(variants, "raw", artifact_dir=artifact_dir, root=root),
        finished_paths=_resolved_metadata_paths(variants, "finished", artifact_dir=artifact_dir, root=root),
        learning_coverage=_coverage_refs(payload),
    )


def _from_postprocess_sweep(metadata_path: Path, payload: Mapping[str, Any], root: Path) -> ArtifactDescriptor:
    artifact_dir = metadata_path.parent
    variants = _mapping_items(payload.get("variants"))
    return ArtifactDescriptor(
        id=_metadata_artifact_id(metadata_path, root),
        artifact_type="postprocess_sweep",
        status="exploratory",
        root=_relative_or_absolute(artifact_dir, root),
        metadata=_relative_or_absolute(metadata_path, root),
        preview=_first_existing(
            ["contact_sheet.png", *_metadata_values(variants, "finished")],
            artifact_dir=artifact_dir,
            root=root,
        ),
        source_cue=str(payload.get("source_raw") or "postprocess sweep"),
        pick_handles=_metadata_names(variants),
        finished_paths=_resolved_metadata_paths(variants, "finished", artifact_dir=artifact_dir, root=root),
        learning_coverage=_coverage_refs(payload),
    )


def _from_selected_render(metadata_path: Path, payload: Mapping[str, Any], root: Path) -> ArtifactDescriptor:
    artifact_dir = metadata_path.parent
    result = payload.get("result") if isinstance(payload.get("result"), Mapping) else {}
    selected = payload.get("selected") if isinstance(payload.get("selected"), Mapping) else {}
    return ArtifactDescriptor(
        id=_metadata_artifact_id(metadata_path, root),
        artifact_type="selected_render",
        status="promoted",
        root=_relative_or_absolute(artifact_dir, root),
        metadata=_relative_or_absolute(metadata_path, root),
        preview=_first_existing([result.get("finished"), result.get("raw")], artifact_dir=artifact_dir, root=root),
        source_cue=str(payload.get("source_sweep") or "selected render"),
        render_profile=_render_config_profile(payload),
        selected_variant=selected.get("name") if isinstance(selected.get("name"), str) else None,
        raw_paths=tuple(
            path for path in [_path_from_metadata(result.get("raw"), artifact_dir=artifact_dir, root=root)] if path
        ),
        finished_paths=tuple(
            path for path in [_path_from_metadata(result.get("finished"), artifact_dir=artifact_dir, root=root)] if path
        ),
        learning_coverage=_coverage_refs(payload),
    )


def _from_legacy_variants(metadata_path: Path, payload: Mapping[str, Any], root: Path) -> ArtifactDescriptor:
    artifact_dir = metadata_path.parent
    variants = _mapping_items(payload.get("variants"))
    notes = ("legacy variants-only metadata; adapted without rewriting original file",)
    return ArtifactDescriptor(
        id=_metadata_artifact_id(metadata_path, root),
        artifact_type="legacy_gallery",
        status="promising",
        root=_relative_or_absolute(artifact_dir, root),
        metadata=_relative_or_absolute(metadata_path, root),
        preview=_first_existing(
            [*_metadata_values(variants, "finished"), *_metadata_values(variants, "raw")],
            artifact_dir=artifact_dir,
            root=root,
        )
        or _fallback_preview(artifact_dir, root),
        source_cue="legacy sweep metadata with variants",
        pick_handles=_metadata_names(variants),
        raw_paths=_resolved_metadata_paths(variants, "raw", artifact_dir=artifact_dir, root=root),
        finished_paths=_resolved_metadata_paths(variants, "finished", artifact_dir=artifact_dir, root=root),
        compatibility_notes=notes,
    )


def _from_legacy_renders(metadata_path: Path, payload: Mapping[str, Any], root: Path) -> ArtifactDescriptor:
    artifact_dir = metadata_path.parent
    renders = _mapping_items(payload.get("renders"))
    first_note = next((item.get("note") for item in renders if isinstance(item, Mapping) and item.get("note")), None)
    return ArtifactDescriptor(
        id=_metadata_artifact_id(metadata_path, root),
        artifact_type="legacy_gallery",
        status="promising",
        root=_relative_or_absolute(artifact_dir, root),
        metadata=_relative_or_absolute(metadata_path, root),
        preview=_first_existing(
            [*_metadata_values(renders, "finished"), *_metadata_values(renders, "raw")],
            artifact_dir=artifact_dir,
            root=root,
        )
        or _fallback_preview(artifact_dir, root),
        source_cue=str(first_note or "legacy render gallery"),
        pick_handles=_metadata_names(renders),
        raw_paths=_resolved_metadata_paths(renders, "raw", artifact_dir=artifact_dir, root=root),
        finished_paths=_resolved_metadata_paths(renders, "finished", artifact_dir=artifact_dir, root=root),
        compatibility_notes=("legacy renders-list metadata; adapted without rewriting original file",),
    )


def _from_reference_study(metadata_path: Path, payload: Mapping[str, Any], root: Path) -> ArtifactDescriptor:
    artifact_dir = metadata_path.parent
    cue = payload.get("lighting") or payload.get("intent") or payload.get("name") or "legacy reference study"
    return ArtifactDescriptor(
        id=_metadata_artifact_id(metadata_path, root),
        artifact_type="reference_study",
        status="promising",
        root=_relative_or_absolute(artifact_dir, root),
        metadata=_relative_or_absolute(metadata_path, root),
        preview=_fallback_preview(artifact_dir, root),
        source_cue=str(cue),
        compatibility_notes=("scene-specific legacy metadata; preserved as reference_study",),
    )


def descriptor_from_metadata(metadata_path: Path, *, root: Path | None = None) -> ArtifactDescriptor | None:
    root = (root or Path.cwd()).resolve()
    metadata_path = Path(metadata_path)
    payload = json.loads(metadata_path.read_text())
    if not isinstance(payload, Mapping):
        return None
    workflow = payload.get("workflow")
    if isinstance(workflow, Mapping) and workflow.get("stage") == "sweep_grid":
        return _from_workbench_sweep(metadata_path, payload, root)
    if payload.get("mode") == "postprocess_sweep":
        return _from_postprocess_sweep(metadata_path, payload, root)
    if metadata_path.name == "selected.json" or (
        isinstance(workflow, Mapping) and workflow.get("stage") == "selected_render"
    ):
        return _from_selected_render(metadata_path, payload, root)
    if isinstance(payload.get("variants"), list):
        if "contact_sheet" in payload or "render_config" in payload:
            return _from_workbench_sweep(metadata_path, payload, root)
        return _from_legacy_variants(metadata_path, payload, root)
    if isinstance(payload.get("renders"), list):
        return _from_legacy_renders(metadata_path, payload, root)
    if any(key in payload for key in ("lighting", "intent", "fighters", "resolution", "cycles_samples")):
        return _from_reference_study(metadata_path, payload, root)
    return None


def _metadata_files(path: Path) -> list[Path]:
    if path.is_file() and path.name in {"metadata.json", "selected.json"}:
        return [path]
    if path.is_dir():
        return sorted([*path.rglob("metadata.json"), *path.rglob("selected.json")])
    return []


def scan_artifacts(paths: Iterable[Path], *, root: Path | None = None) -> list[ArtifactDescriptor]:
    root = (root or Path.cwd()).resolve()
    descriptors: list[ArtifactDescriptor] = []
    seen: set[Path] = set()
    for path in paths:
        for metadata_path in _metadata_files(Path(path)):
            resolved = metadata_path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            try:
                descriptor = descriptor_from_metadata(resolved, root=root)
            except (OSError, json.JSONDecodeError, ValueError):
                descriptor = None
            if descriptor is not None:
                descriptors.append(descriptor)
    return sorted(descriptors, key=lambda item: (item.artifact_type, item.id))


def build_artifact_index(paths: Iterable[Path], *, root: Path | None = None) -> dict[str, Any]:
    root = (root or Path.cwd()).resolve()
    descriptors = scan_artifacts(paths, root=root)
    return {
        "schema_version": ARTIFACT_INDEX_SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "root": str(root),
        "artifacts": [asdict(descriptor) for descriptor in descriptors],
    }


def validate_artifact_index(index: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if index.get("schema_version") != ARTIFACT_INDEX_SCHEMA:
        errors.append(f"schema_version must be {ARTIFACT_INDEX_SCHEMA}")
    artifacts = index.get("artifacts")
    if not isinstance(artifacts, list):
        return [*errors, "artifacts must be a list"]
    for idx, item in enumerate(artifacts, start=1):
        if not isinstance(item, Mapping):
            errors.append(f"artifact {idx} must be an object")
            continue
        if item.get("artifact_type") not in ARTIFACT_TYPES:
            errors.append(f"artifact {idx} has unknown artifact_type {item.get('artifact_type')!r}")
        if item.get("status") not in ARTIFACT_STATUSES:
            errors.append(f"artifact {idx} has unknown status {item.get('status')!r}")
        for key in ("id", "root"):
            if not isinstance(item.get(key), str) or not item.get(key):
                errors.append(f"artifact {idx} missing {key}")
    return errors


def format_artifact_report(index: Mapping[str, Any]) -> str:
    artifacts = index.get("artifacts") if isinstance(index.get("artifacts"), list) else []
    lines = ["Artifact index:", ""]
    if not artifacts:
        lines.append("- no artifacts found")
        return "\n".join(lines)
    for item in artifacts:
        if not isinstance(item, Mapping):
            continue
        lines.append(f"- {item.get('id')}: {item.get('artifact_type')} / {item.get('status')}")
        lines.append(f"  preview: {item.get('preview') or '(none)'}")
        lines.append(f"  source: {item.get('source_cue') or '(none)'}")
    return "\n".join(lines)
