from __future__ import annotations

import importlib
import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any


FIXTURE_REGISTRY_SCHEMA = 1
DEFAULT_FIXTURE_REGISTRY = Path("fixtures") / "registry.json"


class FixtureError(ValueError):
    pass


@dataclass(frozen=True)
class FixtureStatus:
    name: str
    kind: str | None
    present: bool
    detail: str
    missing_dependencies: tuple[str, ...] = ()


def default_fixture_registry(root: Path | None = None) -> Path:
    root = root or Path.cwd()
    return root / DEFAULT_FIXTURE_REGISTRY


def load_fixture_registry(path: Path | None = None, *, root: Path | None = None) -> dict[str, Any]:
    registry_path = path or default_fixture_registry(root)
    payload = json.loads(registry_path.read_text())
    if not isinstance(payload, dict):
        raise FixtureError(f"{registry_path} must contain a JSON object")
    errors = validate_fixture_registry(payload)
    if errors:
        raise FixtureError("\n".join(errors))
    return payload


def validate_fixture_registry(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema") != FIXTURE_REGISTRY_SCHEMA:
        errors.append(f"schema must be {FIXTURE_REGISTRY_SCHEMA}")
    fixtures = payload.get("fixtures")
    if not isinstance(fixtures, list):
        return [*errors, "fixtures must be a list"]
    seen: set[str] = set()
    for index, fixture in enumerate(fixtures, start=1):
        if not isinstance(fixture, Mapping):
            errors.append(f"fixture {index} must be an object")
            continue
        name = fixture.get("name")
        if not isinstance(name, str) or not name:
            errors.append(f"fixture {index} missing name")
        elif name in seen:
            errors.append(f"fixture {index} duplicate name {name!r}")
        else:
            seen.add(name)
        kind = fixture.get("kind")
        if kind not in {"python_builder", "blend_append", "blend_link"}:
            errors.append(f"fixture {name or index} has unknown kind {kind!r}")
        if kind == "python_builder" and not isinstance(fixture.get("builder"), str):
            errors.append(f"fixture {name or index} missing builder")
        if kind in {"blend_append", "blend_link"} and not isinstance(fixture.get("source"), str):
            errors.append(f"fixture {name or index} missing source")
        for key in ("expected_objects", "expected_cameras", "expected_lights", "dependencies"):
            if key in fixture and not isinstance(fixture.get(key), list):
                errors.append(f"fixture {name or index} {key} must be a list")
    return errors


def fixture_map(registry: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    fixtures = registry.get("fixtures") if isinstance(registry.get("fixtures"), list) else []
    return {fixture["name"]: fixture for fixture in fixtures if isinstance(fixture, Mapping) and isinstance(fixture.get("name"), str)}


def fixture_entry(name: str, *, registry: Mapping[str, Any] | None = None, root: Path | None = None) -> Mapping[str, Any]:
    registry = registry or load_fixture_registry(root=root)
    entry = fixture_map(registry).get(name)
    if entry is None:
        raise FixtureError(f"Unknown fixture {name!r}")
    return entry


def _path_missing(value: str, root: Path) -> bool:
    path = Path(value)
    return not (path if path.is_absolute() else root / path).exists()


def fixture_status(name: str, *, registry: Mapping[str, Any] | None = None, root: Path | None = None) -> FixtureStatus:
    root = root or Path.cwd()
    try:
        entry = fixture_entry(name, registry=registry, root=root)
    except FixtureError as error:
        return FixtureStatus(name=name, kind=None, present=False, detail=str(error))
    missing: list[str] = []
    kind = str(entry.get("kind"))
    if kind in {"blend_append", "blend_link"} and isinstance(entry.get("source"), str) and _path_missing(entry["source"], root):
        missing.append(entry["source"])
    for dependency in entry.get("dependencies", []):
        if isinstance(dependency, str) and _path_missing(dependency, root):
            missing.append(dependency)
    if kind == "python_builder":
        try:
            import_fixture_builder(entry)
        except (ImportError, AttributeError, TypeError) as error:
            return FixtureStatus(name=name, kind=kind, present=False, detail=f"builder import failed: {error}")
    if missing:
        return FixtureStatus(name=name, kind=kind, present=False, detail="missing fixture dependency", missing_dependencies=tuple(missing))
    return FixtureStatus(name=name, kind=kind, present=True, detail="ready")


def fixture_statuses(names: Iterable[str], *, registry: Mapping[str, Any] | None = None, root: Path | None = None) -> tuple[FixtureStatus, ...]:
    name_values = tuple(str(name) for name in names)
    if registry is None:
        try:
            registry = load_fixture_registry(root=root)
        except (OSError, FixtureError) as error:
            return tuple(
                FixtureStatus(name=name, kind=None, present=False, detail=f"fixture registry unavailable: {error}")
                for name in name_values
            )
    return tuple(fixture_status(name, registry=registry, root=root) for name in name_values)


def fixture_provenance(names: Iterable[str], *, registry: Mapping[str, Any] | None = None, root: Path | None = None) -> list[dict[str, Any]]:
    registry = registry or load_fixture_registry(root=root)
    provenance = []
    for name in names:
        entry = fixture_entry(str(name), registry=registry, root=root)
        provenance.append(
            {
                "name": entry.get("name"),
                "version": entry.get("version"),
                "kind": entry.get("kind"),
                "source": entry.get("source"),
                "builder": entry.get("builder"),
                "link_mode": entry.get("link_mode"),
                "single_user": entry.get("single_user"),
                "expected_objects": entry.get("expected_objects", []),
                "expected_cameras": entry.get("expected_cameras", []),
                "expected_lights": entry.get("expected_lights", []),
            }
        )
    return provenance


def import_fixture_builder(entry: Mapping[str, Any]) -> Callable[..., Any]:
    spec = entry.get("builder")
    if not isinstance(spec, str) or ":" not in spec:
        raise TypeError("builder must be written as module:callable")
    module_name, attr = spec.split(":", 1)
    target: Any = importlib.import_module(module_name)
    for part in attr.split("."):
        target = getattr(target, part)
    if not callable(target):
        raise TypeError(f"{spec} is not callable")
    return target


def fixture_builder(name: str, *, registry: Mapping[str, Any] | None = None, root: Path | None = None) -> Callable[..., Any]:
    return import_fixture_builder(fixture_entry(name, registry=registry, root=root))


def build_structured_transparency_background(*_args, **_kwargs) -> None:
    """Placeholder builder entrypoint for scouts that need stripe/grid/depth cues."""
    import bpy  # noqa: F401


def build_studio_tabletop_fixture(*_args, **_kwargs) -> None:
    """Placeholder builder entrypoint for pack-shot and material-read scouts."""
    import bpy  # noqa: F401


def build_horizon_depth_stage(*_args, **_kwargs) -> None:
    """Placeholder builder entrypoint for terrain, atmosphere, and depth-read scouts."""
    import bpy  # noqa: F401


def build_material_test_props(*_args, **_kwargs) -> None:
    """Placeholder builder entrypoint for reusable material comparison props."""
    import bpy  # noqa: F401


def format_fixture_report(statuses: Iterable[FixtureStatus]) -> str:
    lines = ["Fixture preflight:", ""]
    for status in statuses:
        state = "ready" if status.present else "missing"
        lines.append(f"- {status.name}: {state}; {status.detail}")
        if status.missing_dependencies:
            lines.append(f"  missing: {', '.join(status.missing_dependencies)}")
    return "\n".join(lines)
