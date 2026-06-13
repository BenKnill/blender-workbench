from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from blender_workbench.presets import RENDER_PRESETS, TILE_PRESETS
from blender_workbench.recipes.diffuser_light_object import (
    DIFFUSER_LIGHT_OBJECT_CAMERA,
    build_diffuser_light_object_scene,
    diffuser_light_object_variants,
)
from blender_workbench.sweep import render_selected_from_sweep, render_sweep


OUT = ROOT / "examples" / "output" / "diffuser_light_object_scout"


def _script_args(argv: list[str] | None = None) -> list[str]:
    values = list(sys.argv[1:] if argv is None else argv)
    if "--" in values:
        return values[values.index("--") + 1 :]
    return values


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render visible translucent diffuser light-object scout cases.")
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
            camera_name=DIFFUSER_LIGHT_OBJECT_CAMERA,
            tile=TILE_PRESETS["hero_pair"],
        )
        render_selected_from_sweep(
            sweep_dir=OUT,
            pick=args.pick,
            build_scene=build_diffuser_light_object_scene,
            root=ROOT,
            config=config,
            postprocess=None,
            title="Diffuser Light Object Selected Render",
            notes=[
                "Promoted from a visible translucent diffuser-object board with receiver diagnostics.",
                "Use this for china-ball, lantern, and printed-shell light props; mesh_light_scout and subsurface_scout answer adjacent but different questions.",
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
        samples=22,
        camera_name=DIFFUSER_LIGHT_OBJECT_CAMERA,
        tile=TILE_PRESETS["auto_square_moodboard"],
    )
    render_sweep(
        variants=diffuser_light_object_variants(),
        build_scene=build_diffuser_light_object_scene,
        out_dir=OUT,
        root=ROOT,
        config=config,
        postprocess=None,
        title="Visible Diffuser Light Object Scout",
        notes=[
            "Fixed receivers; translucent shell opacity, transmission, SSS, emitter size/strength, print density, shape, tint, softness, and distance change.",
            "Judge both the visible light prop and the illumination it casts on matte hard-surface, organic, and glossy receivers.",
        ],
        square=True,
        promotion_command="/Applications/Blender.app/Contents/MacOS/Blender --background --python examples/diffuser_light_object_scout.py -- --pick {pick}",
    )


if __name__ == "__main__":
    main()
