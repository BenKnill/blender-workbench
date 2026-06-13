from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from blender_workbench.presets import RENDER_PRESETS, TILE_PRESETS
from blender_workbench.recipes.depth_of_field import (
    DEPTH_OF_FIELD_CAMERA,
    build_depth_of_field_scene,
    depth_of_field_variants,
)
from blender_workbench.sweep import render_selected_from_sweep, render_sweep


OUT = ROOT / "examples" / "output" / "depth_of_field_scout"


def _script_args(argv: list[str] | None = None) -> list[str]:
    values = list(sys.argv[1:] if argv is None else argv)
    if "--" in values:
        return values[values.index("--") + 1 :]
    return values


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render depth-of-field and focal blur diagnostic scout cases.")
    parser.add_argument("--pick", help="variant name, label, or 1-based index to render with the hero profile")
    parser.add_argument("--hero-samples", type=int, default=96, help="Cycles samples for --pick")
    parser.add_argument("--save-blend", action="store_true", help="also save a selected .blend for viewport review")
    parser.add_argument("--export-blend-only", action="store_true", help="save the selected .blend and skip image rendering")
    args, _unknown = parser.parse_known_args(_script_args(argv))
    return args


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if args.pick:
        config = replace(
            RENDER_PRESETS["hero_check"],
            resolution_x=1280,
            resolution_y=820,
            samples=args.hero_samples,
            camera_name=DEPTH_OF_FIELD_CAMERA,
            tile=TILE_PRESETS["hero_pair"],
        )
        render_selected_from_sweep(
            sweep_dir=OUT,
            pick=args.pick,
            build_scene=build_depth_of_field_scene,
            root=ROOT,
            config=config,
            postprocess=None,
            title="Depth Of Field Selected Render",
            notes=[
                "Promoted from a focal blur scout with foreground, subject, background, and highlight diagnostics.",
                "Use this to confirm focus landing and blur readability before copying camera DOF values into a product or miniature scene.",
            ],
            source_sweep_dir=OUT,
            save_blend=args.save_blend or args.export_blend_only,
            render_image=not args.export_blend_only,
        )
        return

    config = replace(
        RENDER_PRESETS["cycles_preview"],
        resolution_x=620,
        resolution_y=420,
        samples=20,
        camera_name=DEPTH_OF_FIELD_CAMERA,
        tile=TILE_PRESETS["auto_square_moodboard"],
    )
    render_sweep(
        variants=depth_of_field_variants(),
        build_scene=build_depth_of_field_scene,
        out_dir=OUT,
        root=ROOT,
        config=config,
        postprocess=None,
        title="Depth Of Field And Focal Blur Scout",
        notes=[
            "Fixed diagnostic scene; only focus plane, f-stop, lens, foreground occluders, background marker density, and bokeh highlights change.",
            "Use this separate from camera_perspective_scout: perspective controls composition, while this board tests focus correctness and blur readability.",
        ],
        square=True,
        promotion_command="/Applications/Blender.app/Contents/MacOS/Blender --background --python examples/depth_of_field_scout.py -- --pick {pick}",
    )


if __name__ == "__main__":
    main()
