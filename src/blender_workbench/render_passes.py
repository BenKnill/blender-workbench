from __future__ import annotations

import dataclasses
import json
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .sweep import RenderConfig, RenderResult, TileSpec, configure_render, settings_to_jsonable, write_contact_sheet


@dataclass(frozen=True)
class PassSpec:
    name: str
    label: str
    outputs: tuple[str, ...]
    enable_flags: tuple[str, ...] = ()
    note: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "outputs", tuple(self.outputs))
        object.__setattr__(self, "enable_flags", tuple(self.enable_flags))


@dataclass(frozen=True)
class PassTile:
    name: str
    label: str
    output: str | None = None
    path: str | None = None
    available: bool = True
    warning: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class PassDiagnosticReport:
    title: str
    tiles: tuple[PassTile, ...]
    source_scene_settings: Any = None
    render_config: Any = None
    notes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    render_seconds: float | None = None
    contact_sheet: str | None = None


def default_pass_specs() -> tuple[PassSpec, ...]:
    return (
        PassSpec("combined", "combined", ("Image", "Combined"), note="beauty pass before compositor looks"),
        PassSpec("diffuse_color", "diffuse color", ("DiffCol", "Diffuse Color"), ("use_pass_diffuse_color",)),
        PassSpec("diffuse_direct", "diffuse direct", ("DiffDir", "Diffuse Direct"), ("use_pass_diffuse_direct",)),
        PassSpec("glossy_direct", "glossy/spec", ("GlossDir", "Glossy Direct"), ("use_pass_glossy_direct",)),
        PassSpec("emission", "emission", ("Emit", "Emission"), ("use_pass_emit",)),
        PassSpec("ambient_occlusion", "ambient occlusion", ("AO", "Ambient Occlusion"), ("use_pass_ambient_occlusion",)),
        PassSpec("shadow", "shadow", ("Shadow",), ("use_pass_shadow",)),
        PassSpec("depth", "depth/Z", ("Depth", "Z"), ("use_pass_z",)),
        PassSpec("normal", "normal", ("Normal",), ("use_pass_normal",)),
        PassSpec("alpha", "alpha matte", ("Alpha",), note="matte/transparency read when available"),
    )


def coerce_pass_specs(specs: Iterable[PassSpec | Mapping[str, Any]] | None = None) -> tuple[PassSpec, ...]:
    if specs is None:
        return default_pass_specs()
    values: list[PassSpec] = []
    for index, spec in enumerate(specs, start=1):
        if isinstance(spec, PassSpec):
            values.append(spec)
            continue
        data = dict(spec)
        name = str(data.get("name") or "").strip()
        label = str(data.get("label") or name).strip()
        raw_outputs = data.get("outputs", data.get("output", name))
        outputs = (raw_outputs,) if isinstance(raw_outputs, str) else tuple(str(value) for value in raw_outputs)
        raw_flags = data.get("enable_flags", data.get("enable_flag", ()))
        enable_flags = (raw_flags,) if isinstance(raw_flags, str) else tuple(str(value) for value in raw_flags)
        if not name:
            raise ValueError(f"pass spec {index} missing name")
        if not outputs:
            raise ValueError(f"pass spec {name!r} missing outputs")
        values.append(PassSpec(name=name, label=label or name, outputs=outputs, enable_flags=enable_flags, note=data.get("note")))
    return tuple(values)


def pass_tiles_to_results(tiles: Iterable[PassTile], *, root: Path) -> list[RenderResult]:
    results: list[RenderResult] = []
    for tile in tiles:
        if not tile.available or not tile.path:
            continue
        results.append(
            RenderResult(
                name=tile.name,
                raw=tile.path,
                finished=None,
                settings={"pass": tile.name, "output": tile.output},
                label=tile.label,
                note=tile.note,
                tags=("render_pass",),
            )
        )
    return results


def write_pass_diagnostic_metadata(report: PassDiagnosticReport, out_dir: Path) -> Path:
    payload = {
        "mode": "render_pass_diagnostics",
        "title": report.title,
        "notes": list(report.notes),
        "source_scene_settings": settings_to_jsonable(report.source_scene_settings),
        "render_config": settings_to_jsonable(report.render_config),
        "render_seconds": report.render_seconds,
        "contact_sheet": report.contact_sheet,
        "passes": [dataclasses.asdict(tile) for tile in report.tiles],
        "unavailable_passes": [dataclasses.asdict(tile) for tile in report.tiles if not tile.available],
        "warnings": list(report.warnings),
        "workflow": {
            "stage": "render_pass_diagnostics",
            "before_compositor_look_sweep": True,
            "fixed_scene_camera_and_settings": True,
        },
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "metadata.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path


def format_pass_diagnostic_readme(report: PassDiagnosticReport) -> str:
    lines = [f"# {report.title}", "", "Render-pass diagnostic contact sheet.", ""]
    for note in report.notes:
        lines.append(f"- {note}")
    if report.notes:
        lines.append("")
    lines.extend(["## Passes", ""])
    for tile in report.tiles:
        status = "available" if tile.available else "unavailable"
        detail = f" -> `{tile.path}`" if tile.path else ""
        warning = f" ({tile.warning})" if tile.warning else ""
        lines.append(f"- `{tile.name}`: {tile.label}; {status}{detail}{warning}")
    if report.warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in report.warnings)
    lines.extend(
        [
            "",
            "Use this before final-look or compositor sweeps so shadow, AO, depth, normal, emission, and alpha problems are visible before a grade hides them.",
            "",
        ]
    )
    return "\n".join(lines)


def write_pass_diagnostic_readme(report: PassDiagnosticReport, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "README.md"
    path.write_text(format_pass_diagnostic_readme(report))
    return path


def write_pass_diagnostic_outputs(
    report: PassDiagnosticReport,
    *,
    out_dir: Path,
    root: Path,
    tile: TileSpec | None = None,
) -> PassDiagnosticReport:
    out_dir.mkdir(parents=True, exist_ok=True)
    tile = tile or TileSpec.filmstrip(columns=5)
    contact_sheet = out_dir / "contact_sheet.png"
    results = pass_tiles_to_results(report.tiles, root=root)
    if results:
        write_contact_sheet(results, root, contact_sheet, tile)
    report = dataclasses.replace(report, contact_sheet=str(contact_sheet.relative_to(root)) if contact_sheet.exists() else None)
    write_pass_diagnostic_metadata(report, out_dir)
    write_pass_diagnostic_readme(report, out_dir)
    return report


def _enable_view_layer_passes(view_layer: Any, specs: tuple[PassSpec, ...]) -> tuple[str, ...]:
    warnings: list[str] = []
    for spec in specs:
        for flag in spec.enable_flags:
            if hasattr(view_layer, flag):
                try:
                    setattr(view_layer, flag, True)
                except Exception as error:  # Blender versions differ here.
                    warnings.append(f"{spec.name}: could not enable {flag}: {error}")
            else:
                warnings.append(f"{spec.name}: view layer has no {flag}")
    return tuple(warnings)


def _render_layer_output(render_layers: Any, spec: PassSpec) -> tuple[str | None, str | None]:
    available = {output.name: output for output in render_layers.outputs}
    for output_name in spec.outputs:
        if output_name in available:
            return output_name, None
    return None, f"no Render Layers output matching {', '.join(spec.outputs)}"


def _clear_file_slots(file_node: Any) -> None:
    try:
        while len(file_node.file_slots):
            file_node.file_slots.remove(file_node.file_slots[0])
    except Exception:
        pass


def _first_rendered_file(pass_dir: Path, name: str) -> Path | None:
    matches = sorted(pass_dir.glob(f"{name}_*.png"))
    if matches:
        return matches[0]
    direct = pass_dir / f"{name}.png"
    return direct if direct.exists() else None


def render_pass_diagnostic_sheet(
    *,
    build_scene: Callable[[Any], None],
    out_dir: Path,
    root: Path | None = None,
    scene_settings: Any = None,
    config: RenderConfig | None = None,
    pass_specs: Iterable[PassSpec | Mapping[str, Any]] | None = None,
    title: str = "Render Pass Diagnostics",
    notes: Iterable[str] = (),
    tile: TileSpec | None = None,
) -> PassDiagnosticReport:
    import bpy

    root = root or Path.cwd()
    out_dir = Path(out_dir)
    pass_dir = out_dir / "passes"
    pass_dir.mkdir(parents=True, exist_ok=True)
    specs = coerce_pass_specs(pass_specs)
    cfg = config or RenderConfig.cycles_preview()

    start = time.time()
    build_scene(scene_settings)
    engine = configure_render(cfg)
    scene = bpy.context.scene
    view_layer = bpy.context.view_layer
    warnings = list(_enable_view_layer_passes(view_layer, specs))
    scene.use_nodes = True
    tree = scene.node_tree
    tree.nodes.clear()
    render_layers = tree.nodes.new(type="CompositorNodeRLayers")
    file_node = tree.nodes.new(type="CompositorNodeOutputFile")
    file_node.base_path = str(pass_dir)
    file_node.format.file_format = "PNG"
    file_node.format.color_mode = "RGBA"
    _clear_file_slots(file_node)

    linked: list[tuple[PassSpec, str]] = []
    tiles: list[PassTile] = []
    for spec in specs:
        output_name, warning = _render_layer_output(render_layers, spec)
        if not output_name:
            tiles.append(PassTile(spec.name, spec.label, available=False, warning=warning, note=spec.note))
            continue
        slot = file_node.file_slots.new(spec.name)
        slot.path = f"{spec.name}_"
        tree.links.new(render_layers.outputs[output_name], slot)
        linked.append((spec, output_name))

    if linked:
        bpy.ops.render.render(write_still=False)
    else:
        warnings.append("no render passes were available to link")

    for spec, output_name in linked:
        path = _first_rendered_file(pass_dir, spec.name)
        if path:
            tiles.append(
                PassTile(
                    name=spec.name,
                    label=spec.label,
                    output=output_name,
                    path=str(path.relative_to(root)),
                    available=True,
                    note=spec.note,
                )
            )
        else:
            tiles.append(
                PassTile(
                    name=spec.name,
                    label=spec.label,
                    output=output_name,
                    available=False,
                    warning="linked pass did not write a PNG",
                    note=spec.note,
                )
            )

    report = PassDiagnosticReport(
        title=title,
        tiles=tuple(tiles),
        source_scene_settings=scene_settings,
        render_config={**settings_to_jsonable(cfg), "resolved_engine": engine},
        notes=tuple(notes),
        warnings=tuple(warnings),
        render_seconds=round(time.time() - start, 3),
    )
    return write_pass_diagnostic_outputs(report, out_dir=out_dir, root=root, tile=tile)
