from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from blender_workbench.presets import RENDER_PRESETS, TILE_PRESETS
from blender_workbench.recipes.metal_edge_light import (
    METAL_EDGE_LIGHT_CAMERA,
    build_metal_edge_light_scene,
    metal_edge_light_variants,
)
from blender_workbench.sweep import render_selected_from_sweep, render_sweep


OUT = ROOT / "examples" / "output" / "metal_edge_light_scout"


def _script_args(argv: list[str] | None = None) -> list[str]:
    values = list(sys.argv[1:] if argv is None else argv)
    if "--" in values:
        return values[values.index("--") + 1 :]
    return values


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a hard-surface metal and edge-light scout board.")
    parser.add_argument("--pick", help="variant name, label, or 1-based index to render with the hero profile")
    parser.add_argument("--hero-samples", type=int, default=96, help="Cycles samples for --pick")
    args, _unknown = parser.parse_known_args(_script_args(argv))
    return args


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    variants = metal_edge_light_variants()
    if args.pick:
        config = replace(
            RENDER_PRESETS["hero_check"],
            samples=args.hero_samples,
            camera_name=METAL_EDGE_LIGHT_CAMERA,
            tile=TILE_PRESETS["hero_pair"],
        )
        render_selected_from_sweep(
            sweep_dir=OUT,
            pick=args.pick,
            build_scene=build_metal_edge_light_scene,
            root=ROOT,
            config=config,
            postprocess=None,
            title="Metal Edge-Light Selected Render",
            notes=[
                "Promoted from a metal roughness, bevel, scratch, and rim-light board.",
                "Use this heavier pass only after the edge highlight survives the diagnostic forms.",
            ],
            source_sweep_dir=OUT,
        )
        return

    config = replace(
        RENDER_PRESETS["cycles_preview"],
        resolution_x=640,
        resolution_y=440,
        samples=24,
        camera_name=METAL_EDGE_LIGHT_CAMERA,
        tile=TILE_PRESETS["auto_square_moodboard"],
    )
    render_sweep(
        variants=variants,
        build_scene=build_metal_edge_light_scene,
        out_dir=OUT,
        root=ROOT,
        config=config,
        postprocess=None,
        title="Hard-Surface Metal Edge-Light Scout",
        notes=[
            "Hard-surface diagnostic forms: bevelled block, cylinder, thin edge, and curved contrast form.",
            "Sweep roughness, scratches, bevel scale, rim strength/size/color, key/fill, and explicit failure anchors.",
        ],
        square=True,
        promotion_command="/Applications/Blender.app/Contents/MacOS/Blender --background --python examples/metal_edge_light_scout.py -- --pick {pick}",
    )


if __name__ == "__main__":
    main()
