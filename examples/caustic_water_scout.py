from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from blender_workbench.presets import RENDER_PRESETS, TILE_PRESETS
from blender_workbench.recipes.caustic_water import CAUSTIC_WATER_CAMERA, build_caustic_water_scene, caustic_water_variants
from blender_workbench.sweep import render_selected_from_sweep, render_sweep


OUT = ROOT / "examples" / "output" / "caustic_water_scout"


def _script_args(argv: list[str] | None = None) -> list[str]:
    values = list(sys.argv[1:] if argv is None else argv)
    if "--" in values:
        return values[values.index("--") + 1 :]
    return values


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render fake/procedural caustic water scout cases.")
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
            camera_name=CAUSTIC_WATER_CAMERA,
            tile=TILE_PRESETS["hero_pair"],
        )
        render_selected_from_sweep(
            sweep_dir=OUT,
            pick=args.pick,
            build_scene=build_caustic_water_scene,
            root=ROOT,
            config=config,
            postprocess=None,
            title="Caustic Water Selected Render",
            notes=[
                "Promoted from a fake/procedural caustic board with structured receiver diagnostics.",
                "Use this before expensive physical caustics; the metadata records water roughness, caustic scale, light size, contrast, and tint.",
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
        max_bounces=5,
        camera_name=CAUSTIC_WATER_CAMERA,
        tile=TILE_PRESETS["auto_square_moodboard"],
    )
    render_sweep(
        variants=caustic_water_variants(),
        build_scene=build_caustic_water_scene,
        out_dir=OUT,
        root=ROOT,
        config=config,
        postprocess=None,
        title="Caustic Water Scout",
        notes=[
            "Fake/procedural caustic ribbons over a structured floor and wall; water roughness, pattern scale, light size, strength, contrast, and tint change.",
            "This is the fast controllable guardrail before physically correct caustics.",
        ],
        square=True,
        promotion_command="/Applications/Blender.app/Contents/MacOS/Blender --background --python examples/caustic_water_scout.py -- --pick {pick}",
    )


if __name__ == "__main__":
    main()
