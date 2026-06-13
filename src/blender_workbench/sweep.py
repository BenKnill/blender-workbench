from __future__ import annotations

import dataclasses
import json
import math
import shutil
import subprocess
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SweepVariant:
    name: str
    settings: Any
    label: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class RenderResult:
    name: str
    raw: str
    finished: str | None
    settings: Any
    label: str | None = None
    note: str | None = None
    build_seconds: float | None = None
    render_seconds: float | None = None
    postprocess_seconds: float | None = None
    skipped_existing: bool = False


@dataclass(frozen=True)
class TileSpec:
    width: int = 112
    height: int = 112
    columns: int | None = None
    label_height: int = 14
    background: str = "black"
    show_notes: bool = False
    label_max_chars: int | None = 12
    label_point_size: int | None = None

    @classmethod
    def hero_pair(cls) -> "TileSpec":
        return cls(width=360, height=360, columns=2, label_height=28, show_notes=True, label_max_chars=42)

    @classmethod
    def balanced_grid(cls) -> "TileSpec":
        return cls(width=160, height=160, columns=None, label_height=18, label_max_chars=18)

    @classmethod
    def micro_grid(cls, columns: int = 8) -> "TileSpec":
        return cls(width=104, height=104, columns=columns, label_height=14, label_max_chars=12)

    @classmethod
    def auto_micro_grid(cls) -> "TileSpec":
        return cls(width=104, height=104, columns=None, label_height=14, label_max_chars=12)

    @classmethod
    def tiny_grid(cls, columns: int = 10) -> "TileSpec":
        return cls(width=88, height=88, columns=columns, label_height=12, label_max_chars=14)

    @classmethod
    def auto_tiny_grid(cls) -> "TileSpec":
        return cls(width=88, height=88, columns=None, label_height=12, label_max_chars=14)

    @classmethod
    def square_moodboard(cls, columns: int = 5) -> "TileSpec":
        return cls(width=176, height=176, columns=columns, label_height=20, label_max_chars=20)

    @classmethod
    def auto_square_moodboard(cls) -> "TileSpec":
        return cls(width=176, height=176, columns=None, label_height=20, label_max_chars=20)

    @classmethod
    def filmstrip(cls, columns: int = 6) -> "TileSpec":
        return cls(width=280, height=170, columns=columns, label_height=24, label_max_chars=32)

    def columns_for_count(self, count: int) -> int:
        if self.columns is not None:
            return max(1, self.columns)
        return max(1, math.ceil(math.sqrt(max(1, count))))

    def with_auto_columns(self) -> "TileSpec":
        return dataclasses.replace(self, columns=None)


@dataclass(frozen=True)
class RenderConfig:
    resolution_x: int = 960
    resolution_y: int = 630
    engine: str = "CYCLES"
    samples: int = 72
    use_denoising: bool = True
    use_persistent_data: bool = True
    max_bounces: int | None = 6
    transparent_max_bounces: int | None = 16
    view_transform: str = "Filmic"
    look: str = "High Contrast"
    exposure: float = 0.0
    gamma: float = 1.0
    reuse_existing: bool = False
    camera_name: str | None = None
    tile: TileSpec = field(default_factory=TileSpec)

    @classmethod
    def shape_scout(cls) -> "RenderConfig":
        return cls(
            resolution_x=520,
            resolution_y=340,
            engine="BLENDER_WORKBENCH",
            samples=1,
            use_denoising=False,
            transparent_max_bounces=None,
            view_transform="Standard",
            look="Medium High Contrast",
            tile=TileSpec.micro_grid(columns=8),
        )

    @classmethod
    def material_scout(cls) -> "RenderConfig":
        return cls(
            resolution_x=640,
            resolution_y=420,
            engine="EEVEE",
            samples=12,
            use_denoising=False,
            transparent_max_bounces=None,
            view_transform="Filmic",
            look="Medium High Contrast",
            tile=TileSpec.micro_grid(columns=6),
        )

    @classmethod
    def cycles_preview(cls) -> "RenderConfig":
        return cls(
            resolution_x=760,
            resolution_y=500,
            engine="CYCLES",
            samples=32,
            max_bounces=4,
            transparent_max_bounces=18,
            tile=TileSpec.balanced_grid(),
        )

    @classmethod
    def hero_check(cls) -> "RenderConfig":
        return cls(
            resolution_x=1280,
            resolution_y=840,
            engine="CYCLES",
            samples=96,
            max_bounces=8,
            transparent_max_bounces=24,
            tile=TileSpec.hero_pair(),
        )


def settings_to_jsonable(settings: Any) -> Any:
    if dataclasses.is_dataclass(settings):
        return dataclasses.asdict(settings)
    if isinstance(settings, Mapping):
        return dict(settings)
    if hasattr(settings, "__dict__"):
        return dict(settings.__dict__)
    return settings


def grid_variants(
    row_values: Iterable[tuple[str, Mapping[str, Any]]],
    column_values: Iterable[tuple[str, Mapping[str, Any]]],
    *,
    base: Mapping[str, Any] | None = None,
    name_sep: str = "_",
) -> list[SweepVariant]:
    """Build row-major variants from row and column parameter overrides."""
    variants: list[SweepVariant] = []
    base_data = dict(base or {})
    for row_label, row_data in row_values:
        for col_label, col_data in column_values:
            data = dict(base_data)
            data.update(row_data)
            data.update(col_data)
            name = f"{row_label}{name_sep}{col_label}"
            variants.append(SweepVariant(name=name, label=name, settings=data))
    return variants


def named_variants(
    cases: Mapping[str, Mapping[str, Any]] | Iterable[tuple[str, Mapping[str, Any]]],
    *,
    base: Mapping[str, Any] | None = None,
    prefix: str | None = None,
    note: str | None = None,
) -> list[SweepVariant]:
    """Build variants from already-named cases.

    This is the lightest path for moodboards and named explorations where a
    row/column grid would add ceremony instead of clarity.
    """
    case_items = cases.items() if isinstance(cases, Mapping) else cases
    variants: list[SweepVariant] = []
    base_data = dict(base or {})
    for label, settings in case_items:
        data = dict(base_data)
        data.update(settings)
        name = f"{prefix}_{label}" if prefix else label
        variants.append(SweepVariant(name=name, label=label, settings=data, note=note))
    return variants


def _engine_candidates(requested: str) -> tuple[str, ...]:
    aliases = {
        "EEVEE": ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"),
        "BLENDER_EEVEE_NEXT": ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"),
        "WORKBENCH": ("BLENDER_WORKBENCH",),
    }
    return aliases.get(requested, (requested,))


def _set_render_engine(scene: Any, requested: str) -> str:
    for engine in [*_engine_candidates(requested), "CYCLES", "BLENDER_EEVEE", "BLENDER_WORKBENCH"]:
        try:
            scene.render.engine = engine
            return engine
        except TypeError:
            continue
    scene.render.engine = requested
    return requested


def _set_if_present(obj: Any, name: str, value: Any) -> None:
    if hasattr(obj, name):
        setattr(obj, name, value)


def configure_render(config: RenderConfig) -> str:
    import bpy

    scene = bpy.context.scene
    engine = _set_render_engine(scene, config.engine)
    scene.render.resolution_x = config.resolution_x
    scene.render.resolution_y = config.resolution_y
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.view_settings.view_transform = config.view_transform
    scene.view_settings.look = config.look
    scene.view_settings.exposure = config.exposure
    scene.view_settings.gamma = config.gamma

    if engine == "CYCLES" and hasattr(scene, "cycles"):
        scene.cycles.samples = config.samples
        _set_if_present(scene.cycles, "use_denoising", config.use_denoising)
        _set_if_present(scene.cycles, "use_persistent_data", config.use_persistent_data)
        if config.max_bounces is not None:
            _set_if_present(scene.cycles, "max_bounces", config.max_bounces)
        if config.transparent_max_bounces is not None:
            _set_if_present(scene.cycles, "transparent_max_bounces", config.transparent_max_bounces)
    elif engine.startswith("BLENDER_EEVEE") and hasattr(scene, "eevee"):
        _set_if_present(scene.eevee, "taa_render_samples", config.samples)
        _set_if_present(scene.eevee, "taa_samples", config.samples)
    elif engine == "BLENDER_WORKBENCH" and hasattr(scene, "display"):
        shading = getattr(scene.display, "shading", None)
        if shading:
            _set_if_present(shading, "light", "STUDIO")
            _set_if_present(shading, "color_type", "MATERIAL")
    return engine


def configure_cycles(resolution_x: int, resolution_y: int, samples: int) -> None:
    configure_render(RenderConfig(resolution_x=resolution_x, resolution_y=resolution_y, engine="CYCLES", samples=samples))


def postprocess_glow_contrast(raw: Path, finished: Path) -> bool:
    magick = shutil.which("magick")
    if not magick:
        return False
    subprocess.run(
        [
            magick,
            str(raw),
            "-colorspace",
            "sRGB",
            "(",
            "+clone",
            "-blur",
            "0x14",
            "-level",
            "72%,100%",
            ")",
            "-compose",
            "screen",
            "-composite",
            "-sigmoidal-contrast",
            "4,45%",
            "-modulate",
            "104,110,100",
            str(finished),
        ],
        check=True,
    )
    return True


def _label_font_args() -> list[str]:
    for font in [
        "/System/Library/Fonts/SFNS.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
    ]:
        if Path(font).exists():
            return ["-font", font]
    return []


def _label_point_size(tile: TileSpec) -> int:
    if tile.label_point_size is not None:
        return tile.label_point_size
    return max(8, min(13, tile.label_height - 2))


def write_contact_sheet(results: list[RenderResult], root: Path, out_path: Path, tile: TileSpec) -> None:
    magick = shutil.which("magick")
    if not magick or not results:
        return

    columns = tile.columns_for_count(len(results))
    thumbs: list[Path] = []
    for index, result in enumerate(results):
        image_path = root / (result.finished or result.raw)
        thumb = out_path.parent / f"_{index:03d}_{result.name}.thumb.png"
        body_height = max(1, tile.height - tile.label_height)
        label = result.label or result.name
        if tile.show_notes and result.note:
            label = f"{label} - {result.note}"
        label_max_chars = tile.label_max_chars or max(10, tile.width // 8)
        if len(label) > label_max_chars:
            label = f"{label[: max(1, label_max_chars - 3)]}..."
        unlabeled_cmd = [
            magick,
            str(image_path),
            "-resize",
            f"{tile.width}x{tile.height}^",
            "-gravity",
            "center",
            "-extent",
            f"{tile.width}x{tile.height}",
            str(thumb),
        ]
        labeled_cmd = [
            magick,
            str(image_path),
            "-resize",
            f"{tile.width}x{body_height}^",
            "-gravity",
            "center",
            "-extent",
            f"{tile.width}x{body_height}",
            "(",
            "-size",
            f"{tile.width}x{tile.label_height}",
            f"xc:{tile.background}",
            *_label_font_args(),
            "-fill",
            "#f5f0e6",
            "-gravity",
            "center",
            "-pointsize",
            str(_label_point_size(tile)),
            "-annotate",
            "+0+0",
            label,
            ")",
            "-append",
            str(thumb),
        ]
        try:
            subprocess.run(labeled_cmd, check=True)
        except subprocess.CalledProcessError:
            subprocess.run(unlabeled_cmd, check=True)
        thumbs.append(thumb)

    rows: list[Path] = []
    for row_index in range(0, len(thumbs), columns):
        row = out_path.parent / f"_row_{row_index // columns}.png"
        row_paths = list(thumbs[row_index : row_index + columns])
        while len(row_paths) < columns:
            blank = out_path.parent / f"_blank_{row_index}_{len(row_paths)}.png"
            subprocess.run([magick, "-size", f"{tile.width}x{tile.height}", f"xc:{tile.background}", str(blank)], check=True)
            row_paths.append(blank)
            thumbs.append(blank)
        subprocess.run([magick, *[str(path) for path in row_paths], "+append", str(row)], check=True)
        rows.append(row)
    subprocess.run([magick, *[str(path) for path in rows], "-append", str(out_path)], check=True)

    for path in thumbs + rows:
        path.unlink(missing_ok=True)


def write_readme(out_dir: Path, title: str, results: list[RenderResult], notes: list[str] | None = None) -> None:
    lines = [f"# {title}", "", "Rendered variants:", ""]
    for index, result in enumerate(results, start=1):
        detail = f": {result.note}" if result.note else ""
        lines.append(f"{index}. `{Path(result.finished or result.raw).name}`{detail}")
    if notes:
        lines.extend(["", "Notes:", ""])
        lines.extend(f"- {note}" for note in notes)
    lines.extend(["", "`metadata.json` contains the full settings for each tile.", ""])
    (out_dir / "README.md").write_text("\n".join(lines))


def render_sweep(
    *,
    variants: Iterable[SweepVariant],
    build_scene: Callable[[Any], None],
    out_dir: Path,
    root: Path | None = None,
    config: RenderConfig | None = None,
    postprocess: Callable[[Path, Path], bool] | None = postprocess_glow_contrast,
    title: str = "Blender Sweep",
    notes: list[str] | None = None,
    square: bool = False,
) -> list[RenderResult]:
    """Render a sequence of variants from one scene-builder function.

    `build_scene(settings)` should fully rebuild the Blender scene for a variant.
    This function renders each variant, writes raw/finished PNGs, metadata,
    README, and `contact_sheet.png`.
    """
    import bpy

    variant_list = list(variants)
    cfg = config or RenderConfig()
    if square:
        cfg = dataclasses.replace(cfg, tile=cfg.tile.with_auto_columns())
    root = root or Path.cwd()
    out_dir.mkdir(parents=True, exist_ok=True)

    results: list[RenderResult] = []
    sweep_started = time.perf_counter()
    for variant in variant_list:
        raw = out_dir / f"{variant.name}.raw.png"
        finished = out_dir / f"{variant.name}.finished.png"
        wrote_finished = finished.exists()
        if cfg.reuse_existing and raw.exists():
            postprocess_started = time.perf_counter()
            ran_postprocess = False
            if not wrote_finished and postprocess:
                ran_postprocess = True
                wrote_finished = postprocess(raw, finished)
            postprocess_seconds = time.perf_counter() - postprocess_started if ran_postprocess else 0.0
            results.append(
                RenderResult(
                    name=variant.name,
                    raw=str(raw.relative_to(root)),
                    finished=str(finished.relative_to(root)) if wrote_finished else None,
                    settings=settings_to_jsonable(variant.settings),
                    label=variant.label,
                    note=variant.note,
                    postprocess_seconds=postprocess_seconds,
                    skipped_existing=True,
                )
            )
            print(f"Reusing sweep variant {variant.name}")
            continue

        build_started = time.perf_counter()
        build_scene(variant.settings)
        build_seconds = time.perf_counter() - build_started
        engine = configure_render(cfg)
        if cfg.camera_name:
            bpy.context.scene.camera = bpy.data.objects[cfg.camera_name]
        bpy.context.scene.render.filepath = str(raw)
        print(f"Rendering sweep variant {variant.name} ({engine}, {cfg.samples} samples)")
        render_started = time.perf_counter()
        bpy.ops.render.render(write_still=True)
        render_seconds = time.perf_counter() - render_started
        postprocess_started = time.perf_counter()
        wrote_finished = postprocess(raw, finished) if postprocess else False
        postprocess_seconds = time.perf_counter() - postprocess_started
        results.append(
            RenderResult(
                name=variant.name,
                raw=str(raw.relative_to(root)),
                finished=str(finished.relative_to(root)) if wrote_finished else None,
                settings=settings_to_jsonable(variant.settings),
                label=variant.label,
                note=variant.note,
                build_seconds=build_seconds,
                render_seconds=render_seconds,
                postprocess_seconds=postprocess_seconds,
            )
        )

    write_contact_sheet(results, root, out_dir / "contact_sheet.png", cfg.tile)
    write_readme(out_dir, title, results, notes)
    (out_dir / "metadata.json").write_text(
        json.dumps(
            {
                "render_config": settings_to_jsonable(cfg),
                "contact_sheet": {
                    "columns": cfg.tile.columns_for_count(len(results)),
                    "tile": settings_to_jsonable(cfg.tile),
                },
                "total_seconds": time.perf_counter() - sweep_started,
                "variants": [dataclasses.asdict(result) for result in results],
            },
            indent=2,
        )
    )
    return results
