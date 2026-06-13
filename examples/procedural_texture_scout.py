from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from blender_workbench.presets import RENDER_PRESETS, TILE_PRESETS
from blender_workbench.recipes.procedural_texture import (
    PROCEDURAL_TEXTURE_CAMERA,
    build_procedural_texture_scene,
    procedural_texture_variants,
)
from blender_workbench.sweep import render_selected_from_sweep, render_sweep


OUT = ROOT / "examples" / "output" / "procedural_texture_scout"


def _script_args(argv: list[str] | None = None) -> list[str]:
    values = list(sys.argv[1:] if argv is None else argv)
    if "--" in values:
        return values[values.index("--") + 1 :]
    return values


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render reusable procedural surface texture-node scout cases.")
    parser.add_argument("--pick", help="variant name, label, or 1-based index to render with the hero profile")
    parser.add_argument("--hero-samples", type=int, default=96, help="Cycles samples for --pick")
    parser.add_argument("--scale-stride", type=float, default=3.0, help="fine/broad multiplier around the center texture scale")
    parser.add_argument("--contrast-stride", type=float, default=0.24, help="contrast delta for marked and failure anchors")
    parser.add_argument("--bump-stride", type=float, default=0.08, help="bump-strength delta for marked and failure anchors")
    parser.add_argument("--palette-stride", type=float, default=0.18, help="palette-intensity delta for rich and muddy cases")
    args, _unknown = parser.parse_known_args(_script_args(argv))
    return args


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    variants = procedural_texture_variants(
        scale_stride=args.scale_stride,
        contrast_stride=args.contrast_stride,
        bump_stride=args.bump_stride,
        palette_intensity_stride=args.palette_stride,
    )
    if args.pick:
        config = replace(
            RENDER_PRESETS["hero_check"],
            samples=args.hero_samples,
            camera_name=PROCEDURAL_TEXTURE_CAMERA,
            tile=TILE_PRESETS["hero_pair"],
        )
        render_selected_from_sweep(
            sweep_dir=OUT,
            pick=args.pick,
            build_scene=build_procedural_texture_scene,
            root=ROOT,
            config=config,
            postprocess=None,
            title="Procedural Texture Selected Render",
            notes=[
                "Promoted from a surface texture-node board with recorded node descriptors.",
                "Treat this as a material preset seed, not a plume-density or volume-structure preset.",
            ],
            source_sweep_dir=OUT,
        )
        return

    config = replace(
        RENDER_PRESETS["material_scout"],
        resolution_x=640,
        resolution_y=440,
        samples=16,
        camera_name=PROCEDURAL_TEXTURE_CAMERA,
        tile=TILE_PRESETS["auto_square_moodboard"],
    )
    render_sweep(
        variants=variants,
        build_scene=build_procedural_texture_scene,
        out_dir=OUT,
        root=ROOT,
        config=config,
        postprocess=None,
        title="Procedural Texture Node Scout",
        notes=[
            "Fixed subject and lights; texture-node family, scale, ramp contrast, palette, bump, and roughness coupling change.",
            "Use this for reusable surface-shader noise. Plume texture boards test spatial volume structure instead.",
        ],
        square=True,
        promotion_command="/Applications/Blender.app/Contents/MacOS/Blender --background --python examples/procedural_texture_scout.py -- --pick {pick}",
    )


if __name__ == "__main__":
    main()
