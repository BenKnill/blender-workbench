from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from blender_workbench.presets import RENDER_PRESETS, TILE_PRESETS
from blender_workbench.recipes.virtual_set_camera import build_virtual_set_camera_scene, virtual_set_camera_variants
from blender_workbench.sweep import render_selected_from_sweep, render_sweep


OUT = ROOT / "examples" / "output" / "virtual_set_camera_scout"


def _script_args(argv: list[str] | None = None) -> list[str]:
    values = list(sys.argv[1:] if argv is None else argv)
    if "--" in values:
        return values[values.index("--") + 1 :]
    return values


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a multi-camera robustness board for one virtual set.")
    parser.add_argument("--pick", help="camera variant name, label, or 1-based index to render with the hero profile")
    parser.add_argument("--hero-samples", type=int, default=96, help="Cycles samples for --pick")
    args, _unknown = parser.parse_known_args(_script_args(argv))
    return args


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    variants = virtual_set_camera_variants()
    if args.pick:
        config = replace(
            RENDER_PRESETS["hero_check"],
            samples=args.hero_samples,
            tile=TILE_PRESETS["hero_pair"],
        )
        render_selected_from_sweep(
            sweep_dir=OUT,
            pick=args.pick,
            build_scene=build_virtual_set_camera_scene,
            root=ROOT,
            config=config,
            postprocess=None,
            title="Virtual Set Camera Selected Render",
            notes=[
                "Promoted after inspecting the multi-camera robustness board.",
                "Use this heavier pass only after the selected camera preserves set depth and subject read.",
            ],
            source_sweep_dir=OUT,
        )
        return

    config = replace(
        RENDER_PRESETS["cycles_preview"],
        resolution_x=620,
        resolution_y=380,
        samples=24,
        tile=TILE_PRESETS["filmstrip"],
    )
    render_sweep(
        variants=variants,
        build_scene=build_virtual_set_camera_scene,
        out_dir=OUT,
        root=ROOT,
        config=config,
        postprocess=None,
        title="Virtual Set Multi-Camera Scout",
        notes=[
            "Fixed virtual-set scene, six named camera shots, one deliberate failure anchor.",
            "Use after a scene/material/light candidate exists; this is set QA, not a default parameter grid.",
        ],
        promotion_command="/Applications/Blender.app/Contents/MacOS/Blender --background --python examples/virtual_set_camera_scout.py -- --pick {pick}",
    )


if __name__ == "__main__":
    main()
