from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from blender_workbench.presets import RENDER_PRESETS, TILE_PRESETS
from blender_workbench.recipes.layered_material import (
    LAYERED_MATERIAL_CAMERA,
    build_layered_material_scene,
    layered_material_variants,
)
from blender_workbench.sweep import render_selected_from_sweep, render_sweep


OUT = ROOT / "examples" / "output" / "layered_material_scout"


def _script_args(argv: list[str] | None = None) -> list[str]:
    values = list(sys.argv[1:] if argv is None else argv)
    if "--" in values:
        return values[values.index("--") + 1 :]
    return values


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render layered material component contributions for skin and SSS shaders.")
    parser.add_argument("--pick", help="variant name, label, or 1-based index to render with the hero profile")
    parser.add_argument("--hero-samples", type=int, default=96, help="Cycles samples for --pick")
    args, _unknown = parser.parse_known_args(_script_args(argv))
    return args


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    variants = layered_material_variants()
    if args.pick:
        config = replace(
            RENDER_PRESETS["hero_check"],
            samples=args.hero_samples,
            camera_name=LAYERED_MATERIAL_CAMERA,
            tile=TILE_PRESETS["hero_pair"],
        )
        render_selected_from_sweep(
            sweep_dir=OUT,
            pick=args.pick,
            build_scene=build_layered_material_scene,
            root=ROOT,
            config=config,
            postprocess=None,
            title="Layered Material Selected Render",
            notes=[
                "Promoted from a component board that records individual layer weights.",
                "Use the selected metadata as a material preset only after the layer balance reads under a hero profile.",
            ],
            source_sweep_dir=OUT,
        )
        return

    config = replace(
        RENDER_PRESETS["material_scout"],
        resolution_x=640,
        resolution_y=440,
        samples=16,
        camera_name=LAYERED_MATERIAL_CAMERA,
        tile=TILE_PRESETS["auto_square_moodboard"],
    )
    render_sweep(
        variants=variants,
        build_scene=build_layered_material_scene,
        out_dir=OUT,
        root=ROOT,
        config=config,
        postprocess=None,
        title="Layered Skin And SSS Material Scout",
        notes=[
            "Fixed camera, fixed shape, fixed lights; only material layer weights change.",
            "Separate diffuse, shallow/deep SSS, backscatter, broad specular, wet specular, and bump before mixing them.",
            "This complements subsurface_scout: component diagnosis first, finished translucent material direction second.",
        ],
        square=True,
        promotion_command="/Applications/Blender.app/Contents/MacOS/Blender --background --python examples/layered_material_scout.py -- --pick {pick}",
    )


if __name__ == "__main__":
    main()
