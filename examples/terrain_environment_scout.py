from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from blender_workbench.presets import RENDER_PRESETS, TILE_PRESETS
from blender_workbench.recipes.terrain_environment import (
    TERRAIN_ENVIRONMENT_CAMERA,
    build_terrain_environment_scene,
    terrain_environment_variants,
)
from blender_workbench.sweep import render_selected_from_sweep, render_sweep


OUT = ROOT / "examples" / "output" / "terrain_environment_scout"


def _script_args(argv: list[str] | None = None) -> list[str]:
    values = list(sys.argv[1:] if argv is None else argv)
    if "--" in values:
        return values[values.index("--") + 1 :]
    return values


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a terrain environment grid, or promote one picked tile.")
    parser.add_argument("--pick", help="variant name, label, or 1-based index to render with the hero profile")
    parser.add_argument("--hero-samples", type=int, default=96, help="Cycles samples for --pick")
    args, _unknown = parser.parse_known_args(_script_args(argv))
    return args


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    variants = terrain_environment_variants()
    if args.pick:
        config = replace(
            RENDER_PRESETS["hero_check"],
            resolution_x=1280,
            resolution_y=820,
            samples=args.hero_samples,
            camera_name=TERRAIN_ENVIRONMENT_CAMERA,
        )
        render_selected_from_sweep(
            sweep_dir=OUT,
            pick=args.pick,
            build_scene=build_terrain_environment_scene,
            root=ROOT,
            config=config,
            postprocess=None,
            title="Terrain Environment Selected Render",
            notes=[
                "Promoted after inspecting the terrain environment contact sheet.",
                "Use this heavier render to judge horizon mood, strata readability, and foreground depth.",
            ],
            source_sweep_dir=OUT,
        )
        return

    config = replace(
        RENDER_PRESETS["cycles_preview"],
        resolution_x=520,
        resolution_y=340,
        samples=20,
        max_bounces=4,
        camera_name=TERRAIN_ENVIRONMENT_CAMERA,
        tile=TILE_PRESETS["auto_tiny_grid"],
    )
    render_sweep(
        variants=variants,
        build_scene=build_terrain_environment_scene,
        out_dir=OUT,
        root=ROOT,
        config=config,
        postprocess=None,
        title="Terrain Environment Scout",
        notes=[
            "5x5 same-view stride sheet: relief, strata, haze, backlight, and foreground scale.",
            "Inspired by BlenderArt issue 39 landscape/Europa and virtual-environment prompts.",
        ],
        promotion_command="/Applications/Blender.app/Contents/MacOS/Blender --background --python examples/terrain_environment_scout.py -- --pick {pick}",
        square=True,
    )


if __name__ == "__main__":
    main()
