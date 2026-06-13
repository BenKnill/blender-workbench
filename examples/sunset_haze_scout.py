from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from blender_workbench.presets import RENDER_PRESETS, TILE_PRESETS
from blender_workbench.recipes.sunset_haze import SUNSET_HAZE_CAMERA, build_sunset_haze_scene, sunset_haze_variants
from blender_workbench.sweep import render_selected_from_sweep, render_sweep


OUT = ROOT / "examples" / "output" / "sunset_haze_scout"


def _script_args(argv: list[str] | None = None) -> list[str]:
    values = list(sys.argv[1:] if argv is None else argv)
    if "--" in values:
        return values[values.index("--") + 1 :]
    return values


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render an ordered sunset haze filmstrip, or promote one picked tile.")
    parser.add_argument("--pick", help="variant name, label, or 1-based index to render with the hero profile")
    parser.add_argument("--hero-samples", type=int, default=72, help="Cycles samples for --pick")
    args, _unknown = parser.parse_known_args(_script_args(argv))
    return args


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if args.pick:
        config = replace(
            RENDER_PRESETS["hero_check"],
            resolution_x=1280,
            resolution_y=760,
            samples=args.hero_samples,
            camera_name=SUNSET_HAZE_CAMERA,
        )
        render_selected_from_sweep(
            sweep_dir=OUT,
            pick=args.pick,
            build_scene=build_sunset_haze_scene,
            root=ROOT,
            config=config,
            postprocess=None,
            title="Sunset Haze Selected Render",
            notes=[
                "Promoted after inspecting the ordered sunset haze filmstrip.",
                "Use this heavier render to judge horizon depth, disk brightness, and foreground silhouette.",
            ],
        )
        return

    config = replace(
        RENDER_PRESETS["cycles_preview"],
        resolution_x=560,
        resolution_y=340,
        samples=20,
        max_bounces=4,
        camera_name=SUNSET_HAZE_CAMERA,
        tile=TILE_PRESETS["filmstrip"],
    )
    render_sweep(
        variants=sunset_haze_variants(),
        build_scene=build_sunset_haze_scene,
        out_dir=OUT,
        root=ROOT,
        config=config,
        postprocess=None,
        title="Sunset Haze Filmstrip Scout",
        notes=[
            "Ordered filmstrip: flat failure, three SUNSET_HAZE presets, over-orange failure, and washout failure.",
            "Use this for static dusk/moonrise/afterglow mood before long-exposure streak work.",
        ],
        promotion_command="/Applications/Blender.app/Contents/MacOS/Blender --background --python examples/sunset_haze_scout.py -- --pick {pick}",
    )


if __name__ == "__main__":
    main()
