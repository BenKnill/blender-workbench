from __future__ import annotations

import dataclasses
import json
import shutil
import subprocess
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


@dataclass(frozen=True)
class TileSpec:
    width: int = 320
    height: int = 210
    columns: int = 4
    label_height: int = 28
    background: str = "black"

    @classmethod
    def hero_pair(cls) -> "TileSpec":
        return cls(width=440, height=286, columns=2, label_height=30)

    @classmethod
    def balanced_grid(cls) -> "TileSpec":
        return cls(width=320, height=220, columns=3, label_height=28)

    @classmethod
    def micro_grid(cls, columns: int = 8) -> "TileSpec":
        return cls(width=168, height=126, columns=columns, label_height=18)

    @classmethod
    def square_moodboard(cls, columns: int = 5) -> "TileSpec":
        return cls(width=220, height=220, columns=columns, label_height=24)

    @classmethod
    def filmstrip(cls, columns: int = 6) -> "TileSpec":
        return cls(width=280, height=170, columns=columns, label_height=24)


@dataclass(frozen=True)
class RenderConfig:
    resolution_x: int = 960
    resolution_y: int = 630
    samples: int = 72
    camera_name: str | None = None
    tile: TileSpec = field(default_factory=TileSpec)


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


def configure_cycles(resolution_x: int, resolution_y: int, samples: int) -> None:
    import bpy

    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x = resolution_x
    scene.render.resolution_y = resolution_y
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.view_settings.view_transform = "Filmic"
    scene.view_settings.look = "High Contrast"


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


def write_contact_sheet(results: list[RenderResult], root: Path, out_path: Path, tile: TileSpec) -> None:
    magick = shutil.which("magick")
    if not magick:
        return

    thumbs: list[Path] = []
    for index, result in enumerate(results):
        image_path = root / (result.finished or result.raw)
        thumb = out_path.parent / f"_{index:03d}_{result.name}.thumb.png"
        body_height = max(1, tile.height - tile.label_height)
        label = result.label or result.name
        if result.note:
            label = f"{label} - {result.note}"
        if len(label) > 44:
            label = f"{label[:41]}..."
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
            "13",
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
    for row_index in range(0, len(thumbs), tile.columns):
        row = out_path.parent / f"_row_{row_index // tile.columns}.png"
        subprocess.run([magick, *[str(path) for path in thumbs[row_index : row_index + tile.columns]], "+append", str(row)], check=True)
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
) -> list[RenderResult]:
    """Render a sequence of variants from one scene-builder function.

    `build_scene(settings)` should fully rebuild the Blender scene for a variant.
    This function renders each variant, writes raw/finished PNGs, metadata,
    README, and `contact_sheet.png`.
    """
    import bpy

    cfg = config or RenderConfig()
    root = root or Path.cwd()
    out_dir.mkdir(parents=True, exist_ok=True)

    results: list[RenderResult] = []
    for variant in variants:
        build_scene(variant.settings)
        configure_cycles(cfg.resolution_x, cfg.resolution_y, cfg.samples)
        if cfg.camera_name:
            bpy.context.scene.camera = bpy.data.objects[cfg.camera_name]
        raw = out_dir / f"{variant.name}.raw.png"
        finished = out_dir / f"{variant.name}.finished.png"
        bpy.context.scene.render.filepath = str(raw)
        print(f"Rendering sweep variant {variant.name}")
        bpy.ops.render.render(write_still=True)
        wrote_finished = postprocess(raw, finished) if postprocess else False
        results.append(
            RenderResult(
                name=variant.name,
                raw=str(raw.relative_to(root)),
                finished=str(finished.relative_to(root)) if wrote_finished else None,
                settings=settings_to_jsonable(variant.settings),
                label=variant.label,
                note=variant.note,
            )
        )

    write_contact_sheet(results, root, out_dir / "contact_sheet.png", cfg.tile)
    write_readme(out_dir, title, results, notes)
    (out_dir / "metadata.json").write_text(json.dumps({"variants": [dataclasses.asdict(result) for result in results]}, indent=2))
    return results
