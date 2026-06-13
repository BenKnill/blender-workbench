from __future__ import annotations

import dataclasses
import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SceneSanityExpectations:
    expected_camera: str | None = None
    expected_objects: tuple[str, ...] = ()
    expected_lights: tuple[str, ...] = ()
    expected_materials: tuple[str, ...] = ()
    require_world: bool = False
    min_subject_objects: int = 1
    transparent: bool = False
    min_transparent_bounces: int = 8
    warn_unapplied_scale: bool = False
    warn_unapplied_rotation: bool = False


@dataclass(frozen=True)
class SceneSanityWarning:
    code: str
    message: str
    subject: str | None = None
    severity: str = "warning"


@dataclass(frozen=True)
class SceneSanityReport:
    status: str
    strict: bool
    strict_passed: bool
    warnings: tuple[SceneSanityWarning, ...]
    render_config: dict[str, Any]

    @property
    def passed(self) -> bool:
        return self.strict_passed or not self.strict

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "strict": self.strict,
            "passed": self.passed,
            "strict_passed": self.strict_passed,
            "warnings": [dataclasses.asdict(warning) for warning in self.warnings],
            "render_config": self.render_config,
        }


def coerce_scene_expectations(value: SceneSanityExpectations | Mapping[str, Any] | None = None) -> SceneSanityExpectations:
    if value is None:
        return SceneSanityExpectations()
    if isinstance(value, SceneSanityExpectations):
        return value
    data = dict(value)
    for key in ("expected_objects", "expected_lights", "expected_materials"):
        if key in data and data[key] is not None:
            data[key] = tuple(str(item) for item in data[key])
    return SceneSanityExpectations(**data)


def _object_name(obj: Any) -> str:
    return str(getattr(obj, "name", ""))


def _scene_objects(scene: Any) -> tuple[Any, ...]:
    objects = getattr(scene, "objects", None)
    if objects is None:
        return ()
    if isinstance(objects, Mapping):
        return tuple(objects.values())
    try:
        return tuple(objects)
    except TypeError:
        return tuple(objects.values())


def _object_map(objects: Iterable[Any]) -> dict[str, Any]:
    return {_object_name(obj): obj for obj in objects if _object_name(obj)}


def _object_type(obj: Any) -> str:
    return str(getattr(obj, "type", "") or getattr(getattr(obj, "data", None), "type", "")).upper()


def _is_light(obj: Any) -> bool:
    return _object_type(obj) == "LIGHT" or hasattr(getattr(obj, "data", None), "energy")


def _is_camera(obj: Any) -> bool:
    return _object_type(obj) == "CAMERA"


def _is_hidden(obj: Any) -> bool:
    for attr in ("hide_render", "hide_viewport"):
        if bool(getattr(obj, attr, False)):
            return True
    hide_get = getattr(obj, "hide_get", None)
    return bool(hide_get()) if callable(hide_get) else False


def _light_energy(obj: Any) -> float | None:
    energy = getattr(getattr(obj, "data", None), "energy", None)
    try:
        return float(energy)
    except (TypeError, ValueError):
        return None


def _materials_for_object(obj: Any) -> tuple[str, ...]:
    materials = getattr(getattr(obj, "data", None), "materials", None) or ()
    names = []
    for material in materials:
        name = getattr(material, "name", None)
        if name:
            names.append(str(name))
    return tuple(names)


def _tuple_floats(value: Any) -> tuple[float, ...]:
    try:
        return tuple(float(item) for item in value)
    except (TypeError, ValueError):
        return ()


def _is_identity_scale(value: Any) -> bool:
    scale = _tuple_floats(value)
    return bool(scale) and all(abs(item - 1.0) < 1e-4 for item in scale)


def _is_zero_rotation(value: Any) -> bool:
    rotation = _tuple_floats(value)
    return bool(rotation) and all(abs(item) < 1e-4 for item in rotation)


def _config_value(config: Any, key: str) -> Any:
    if isinstance(config, Mapping):
        return config.get(key)
    return getattr(config, key, None)


def _render_config_snapshot(config: Any) -> dict[str, Any]:
    keys = (
        "engine",
        "resolution_x",
        "resolution_y",
        "samples",
        "use_denoising",
        "max_bounces",
        "transparent_max_bounces",
        "camera_name",
    )
    return {key: _config_value(config, key) for key in keys}


def _scene_engine(scene: Any) -> str | None:
    render = getattr(scene, "render", None)
    engine = getattr(render, "engine", None)
    return str(engine) if engine else None


def _engine_matches(actual: str | None, expected: str | None) -> bool:
    if not actual or not expected:
        return True
    if actual == expected:
        return True
    if expected == "EEVEE" and actual.startswith("BLENDER_EEVEE"):
        return True
    return False


def _warn(code: str, message: str, *, subject: str | None = None) -> SceneSanityWarning:
    return SceneSanityWarning(code=code, message=message, subject=subject)


def run_scene_sanity(
    scene: Any,
    *,
    config: Any,
    expectations: SceneSanityExpectations | Mapping[str, Any] | None = None,
    strict: bool = False,
    output_dir: Path | None = None,
) -> SceneSanityReport:
    expected = coerce_scene_expectations(expectations)
    warnings: list[SceneSanityWarning] = []
    config_snapshot = _render_config_snapshot(config)
    objects = _scene_objects(scene)
    by_name = _object_map(objects)

    active_camera = getattr(scene, "camera", None)
    active_camera_name = _object_name(active_camera) if active_camera else None
    expected_camera = expected.expected_camera or config_snapshot.get("camera_name")
    if expected_camera:
        if expected_camera not in by_name:
            warnings.append(_warn("missing_camera", f"Expected camera {expected_camera!r} was not found", subject=expected_camera))
        if active_camera_name != expected_camera:
            warnings.append(
                _warn(
                    "active_camera_mismatch",
                    f"Active camera is {active_camera_name!r}, expected {expected_camera!r}",
                    subject=expected_camera,
                )
            )
    elif not active_camera_name:
        warnings.append(_warn("missing_active_camera", "Scene has no active camera"))

    scene_engine = _scene_engine(scene)
    expected_engine = config_snapshot.get("engine")
    if not _engine_matches(scene_engine, expected_engine):
        warnings.append(_warn("render_engine_mismatch", f"Scene engine is {scene_engine!r}, expected {expected_engine!r}"))

    if expected.require_world and getattr(scene, "world", None) is None:
        warnings.append(_warn("missing_world", "Scene has no world/background configured"))

    for name in expected.expected_objects:
        if name not in by_name:
            warnings.append(_warn("missing_object", f"Expected object {name!r} was not found", subject=name))

    for name in expected.expected_lights:
        light = by_name.get(name)
        if light is None:
            warnings.append(_warn("missing_light", f"Expected light {name!r} was not found", subject=name))
            continue
        energy = _light_energy(light)
        if energy is not None and energy <= 0:
            warnings.append(_warn("zero_energy_light", f"Light {name!r} has nonzero-energy expectation but energy is {energy}", subject=name))

    material_names = {name for obj in objects for name in _materials_for_object(obj)}
    for name in expected.expected_materials:
        if name not in material_names:
            warnings.append(_warn("missing_material", f"Expected material {name!r} was not found", subject=name))

    subject_count = sum(1 for obj in objects if not _is_camera(obj) and not _is_light(obj) and not _is_hidden(obj))
    if subject_count < expected.min_subject_objects:
        warnings.append(
            _warn(
                "empty_or_tiny_scene",
                f"Scene has {subject_count} visible subject object(s), expected at least {expected.min_subject_objects}",
            )
        )

    if expected.transparent:
        transparent_bounces = config_snapshot.get("transparent_max_bounces")
        if transparent_bounces is None or int(transparent_bounces) < expected.min_transparent_bounces:
            warnings.append(
                _warn(
                    "low_transparent_bounces",
                    f"transparent_max_bounces is {transparent_bounces}, expected at least {expected.min_transparent_bounces}",
                )
            )

    if expected.warn_unapplied_scale:
        for obj in objects:
            if not _is_camera(obj) and not _is_light(obj) and not _is_identity_scale(getattr(obj, "scale", ())):
                warnings.append(_warn("unapplied_scale", f"Object {obj.name!r} has non-identity scale", subject=_object_name(obj)))
    if expected.warn_unapplied_rotation:
        for obj in objects:
            if not _is_camera(obj) and not _is_light(obj) and not _is_zero_rotation(getattr(obj, "rotation_euler", ())):
                warnings.append(_warn("unapplied_rotation", f"Object {obj.name!r} has nonzero rotation", subject=_object_name(obj)))

    if output_dir is not None:
        path = Path(output_dir)
        writable_target = path if path.exists() else path.parent
        if writable_target.exists() and not os.access(writable_target, os.W_OK):
            warnings.append(_warn("output_not_writable", f"Output path {path} is not writable", subject=str(path)))

    strict_passed = not warnings
    status = "passed" if strict_passed else "failed" if strict else "warning"
    return SceneSanityReport(
        status=status,
        strict=strict,
        strict_passed=strict_passed,
        warnings=tuple(warnings),
        render_config=config_snapshot,
    )


def summarize_scene_sanity(reports: Iterable[Mapping[str, Any] | SceneSanityReport | None]) -> dict[str, Any] | None:
    values: list[dict[str, Any]] = []
    for report in reports:
        if report is None:
            continue
        if isinstance(report, SceneSanityReport):
            values.append(report.to_jsonable())
        else:
            values.append(dict(report))
    if not values:
        return None
    warnings = []
    seen: set[tuple[str, str | None]] = set()
    for report in values:
        for warning in report.get("warnings", []):
            key = (str(warning.get("code")), warning.get("subject"))
            if key not in seen:
                seen.add(key)
                warnings.append(warning)
    strict = any(bool(report.get("strict")) for report in values)
    strict_passed = all(bool(report.get("strict_passed", not report.get("warnings"))) for report in values)
    if strict and not strict_passed:
        status = "failed"
    elif warnings:
        status = "warning"
    else:
        status = "passed"
    return {
        "status": status,
        "strict": strict,
        "passed": strict_passed or not strict,
        "strict_passed": strict_passed,
        "warnings": warnings,
        "reports": values,
    }


def format_scene_sanity_report(report: SceneSanityReport | Mapping[str, Any]) -> str:
    payload = report.to_jsonable() if isinstance(report, SceneSanityReport) else dict(report)
    lines = [f"Scene sanity: {payload.get('status', 'unknown')}"]
    warnings = payload.get("warnings") or []
    if not warnings:
        lines.append("- no warnings")
    for warning in warnings:
        subject = f" [{warning.get('subject')}]" if warning.get("subject") else ""
        lines.append(f"- {warning.get('code')}{subject}: {warning.get('message')}")
    return "\n".join(lines)
