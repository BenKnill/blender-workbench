from __future__ import annotations

import dataclasses
import json
import shutil
import subprocess
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from blender_workbench.sweep import RenderResult, SweepVariant, TileSpec, _relative_or_absolute, named_variants, settings_to_jsonable, write_contact_sheet


@dataclass(frozen=True)
class PostprocessLookSettings:
    glow_radius: float = 0.0
    glow_gain: float = 0.0
    brightness: float = 0.0
    contrast: float = 0.0
    saturation: float = 100.0
    warmth: float = 0.0
    vignette: float = 0.0


def coerce_postprocess_look_settings(settings: PostprocessLookSettings | Mapping[str, Any] | None = None) -> PostprocessLookSettings:
    if isinstance(settings, PostprocessLookSettings):
        return settings
    data = dataclasses.asdict(PostprocessLookSettings())
    if settings:
        data.update({key: value for key, value in dict(settings).items() if key in data})
    return PostprocessLookSettings(**data)


def postprocess_look_variants(*, prefix: str = "look") -> list[SweepVariant]:
    return named_variants(
        {
            "neutral": {},
            "warm_glow": {"glow_radius": 18.0, "glow_gain": 0.22, "warmth": 6.0, "saturation": 108.0},
            "cool_mist": {"glow_radius": 10.0, "glow_gain": 0.12, "warmth": -7.0, "brightness": -2.0, "saturation": 88.0},
            "high_contrast": {"contrast": 18.0, "brightness": -4.0, "saturation": 104.0},
            "soft_haze": {"glow_radius": 28.0, "glow_gain": 0.16, "contrast": -9.0, "brightness": 4.0, "saturation": 94.0},
            "desat_print": {"contrast": 8.0, "saturation": 68.0, "warmth": 4.0},
            "vivid": {"contrast": 12.0, "saturation": 126.0, "warmth": 2.0},
            "vignette": {"contrast": 8.0, "vignette": 18.0, "saturation": 96.0},
            "overdone_fail": {"glow_radius": 42.0, "glow_gain": 0.46, "contrast": 26.0, "saturation": 142.0, "warmth": 11.0, "vignette": 28.0},
        },
        prefix=prefix,
        note="postprocess look scout: glow, contrast, saturation, warmth, vignette",
    )


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _colorize_args(warmth: float) -> list[str]:
    if warmth == 0:
        return []
    amount = abs(_clamp(warmth, -30.0, 30.0))
    fill = "rgb(255,196,126)" if warmth > 0 else "rgb(120,165,255)"
    return ["-fill", fill, "-colorize", f"{amount}%"]


def magick_look_postprocess(raw: Path, finished: Path, settings: PostprocessLookSettings | Mapping[str, Any] | None = None) -> bool:
    magick = shutil.which("magick")
    if not magick:
        return False

    look = coerce_postprocess_look_settings(settings)
    cmd = [magick, str(raw), "-colorspace", "sRGB"]
    if look.glow_radius > 0 and look.glow_gain > 0:
        cmd.extend(
            [
                "(",
                "+clone",
                "-blur",
                f"0x{look.glow_radius:.3f}",
                "-evaluate",
                "multiply",
                f"{_clamp(look.glow_gain, 0.0, 1.5):.3f}",
                ")",
                "-compose",
                "screen",
                "-composite",
            ]
        )
    cmd.extend(["-brightness-contrast", f"{look.brightness:.3f}x{look.contrast:.3f}"])
    cmd.extend(["-modulate", f"100,{_clamp(look.saturation, 0.0, 220.0):.3f},100"])
    cmd.extend(_colorize_args(look.warmth))
    if look.vignette > 0:
        cmd.extend(["-background", "black", "-vignette", f"0x{look.vignette:.3f}"])
    cmd.append(str(finished))
    subprocess.run(cmd, check=True)
    return True


def write_postprocess_readme(
    out_dir: Path,
    title: str,
    source_raw: Path,
    root: Path,
    results: list[RenderResult],
    notes: list[str] | None = None,
) -> None:
    lines = [
        f"# {title}",
        "",
        f"Source raw: `{_relative_or_absolute(source_raw, root)}`",
        "",
        "Postprocess variants:",
        "",
    ]
    for index, result in enumerate(results, start=1):
        detail = f": {result.note}" if result.note else ""
        lines.append(f"{index}. `{Path(result.finished or result.raw).name}`{detail}")
    if notes:
        lines.extend(["", "Notes:", ""])
        lines.extend(f"- {note}" for note in notes)
    lines.extend(
        [
            "",
            "Next:",
            "",
            "- Pick the most promising look by `name` in `metadata.json`.",
            "- Carry both the source scene settings and look settings into the hero render notes.",
            "",
            "`metadata.json` contains the source image, contact sheet settings, and look settings for each tile.",
            "",
        ]
    )
    (out_dir / "README.md").write_text("\n".join(lines))


def render_postprocess_sweep(
    *,
    raw_image: Path,
    variants: Iterable[SweepVariant],
    out_dir: Path,
    root: Path | None = None,
    tile: TileSpec | None = None,
    processor: Callable[[Path, Path, Any], bool] = magick_look_postprocess,
    title: str = "Postprocess Look Sweep",
    notes: list[str] | None = None,
    square: bool = False,
) -> list[RenderResult]:
    """Apply look variants to one raw image and write a contact sheet."""
    root = (root or Path.cwd()).resolve()
    raw_image = raw_image.resolve()
    if not raw_image.exists():
        raise FileNotFoundError(raw_image)
    variant_list = list(variants)
    tile_spec = tile or TileSpec.auto_square_moodboard()
    if square:
        tile_spec = tile_spec.with_auto_columns()

    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[RenderResult] = []
    sweep_started = time.perf_counter()
    for variant in variant_list:
        finished = out_dir / f"{variant.name}.look.png"
        postprocess_started = time.perf_counter()
        wrote = processor(raw_image, finished, variant.settings)
        postprocess_seconds = time.perf_counter() - postprocess_started
        if not wrote:
            raise RuntimeError("Postprocess processor did not write an output image")
        results.append(
            RenderResult(
                name=variant.name,
                raw=_relative_or_absolute(raw_image, root),
                finished=_relative_or_absolute(finished, root),
                settings=settings_to_jsonable(variant.settings),
                label=variant.label,
                note=variant.note,
                postprocess_seconds=postprocess_seconds,
            )
        )

    write_contact_sheet(results, root, out_dir / "contact_sheet.png", tile_spec)
    write_postprocess_readme(out_dir, title, raw_image, root, results, notes)
    (out_dir / "metadata.json").write_text(
        json.dumps(
            {
                "mode": "postprocess_sweep",
                "source_raw": _relative_or_absolute(raw_image, root),
                "contact_sheet": {
                    "columns": tile_spec.columns_for_count(len(results)),
                    "tile": settings_to_jsonable(tile_spec),
                },
                "total_seconds": time.perf_counter() - sweep_started,
                "variants": [dataclasses.asdict(result) for result in results],
            },
            indent=2,
        )
    )
    return results
