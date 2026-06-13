from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from blender_workbench.presets import RENDER_PRESETS, TILE_PRESETS
from blender_workbench.recipes.rocket_plume import ROCKET_PLUME_CAMERA, build_rocket_plume_scene, rocket_plume_scout_variants
from blender_workbench.sweep import render_selected_from_sweep, render_sweep


OUT = ROOT / "examples" / "output" / "rocket_plume_scout"


def _script_args(argv: list[str] | None = None) -> list[str]:
    values = list(sys.argv[1:] if argv is None else argv)
    if "--" in values:
        return values[values.index("--") + 1 :]
    return values


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a rocket plume scout grid, or promote one picked tile.")
    parser.add_argument("--pick", help="variant name, label, or 1-based index to render with the hero profile")
    parser.add_argument("--hero-samples", type=int, default=96, help="Cycles samples for --pick")
    parser.add_argument("--save-blend", action="store_true", help="also save a selected .blend for GUI review")
    parser.add_argument("--export-blend-only", action="store_true", help="save the selected .blend and skip image rendering")
    args, _unknown = parser.parse_known_args(_script_args(argv))
    return args


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if args.pick:
        config = replace(
            RENDER_PRESETS["hero_check"],
            resolution_x=1280,
            resolution_y=840,
            samples=args.hero_samples,
            camera_name=ROCKET_PLUME_CAMERA,
        )
        render_selected_from_sweep(
            sweep_dir=OUT,
            pick=args.pick,
            build_scene=build_rocket_plume_scene,
            root=ROOT,
            config=config,
            title="Rocket Vacuum Plume Selected Render",
            notes=[
                "Promoted after inspecting the plume contact sheet.",
                "Use this heavier render to judge transparency, plume width, and smoky structure.",
            ],
            save_blend=args.save_blend or args.export_blend_only,
            render_image=not args.export_blend_only,
        )
        return

    config = replace(
        RENDER_PRESETS["cycles_preview"],
        resolution_x=640,
        resolution_y=420,
        samples=24,
        camera_name=ROCKET_PLUME_CAMERA,
        tile=TILE_PRESETS["micro_grid"],
    )
    render_sweep(
        variants=rocket_plume_scout_variants(),
        build_scene=build_rocket_plume_scene,
        out_dir=OUT,
        root=ROOT,
        config=config,
        title="Rocket Vacuum Plume Scout",
        notes=[
            "3x3 scout crossing transparent alpha/strength with broad vacuum-plume shape.",
            "The target is smoky, wide, and structured rather than a narrow orange torch.",
        ],
        promotion_command="/Applications/Blender.app/Contents/MacOS/Blender --background --python examples/rocket_plume_scout.py -- --pick {pick}",
        square=True,
    )


if __name__ == "__main__":
    main()
