from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from blender_workbench.presets import RENDER_PRESETS, TILE_PRESETS
from blender_workbench.recipes.silhouette_shape import SILHOUETTE_SHAPE_CAMERA, build_silhouette_shape_scene, silhouette_shape_variants
from blender_workbench.sweep import render_selected_from_sweep, render_sweep


OUT = ROOT / "examples" / "output" / "silhouette_shape_scout"


def _script_args(argv: list[str] | None = None) -> list[str]:
    values = list(sys.argv[1:] if argv is None else argv)
    if "--" in values:
        return values[values.index("--") + 1 :]
    return values


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a blind silhouette grid, label rerun, or selected shape render.")
    parser.add_argument("--pick", help="variant name, label, or 1-based index to render with the hero profile")
    parser.add_argument("--hero-samples", type=int, default=1, help="Workbench samples for --pick")
    parser.add_argument("--labels", action="store_true", help="rerender the scout with visible labels")
    args, _unknown = parser.parse_known_args(_script_args(argv))
    return args


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    variants = silhouette_shape_variants()
    if args.pick:
        config = replace(
            RENDER_PRESETS["shape_scout"],
            resolution_x=900,
            resolution_y=640,
            samples=args.hero_samples,
            camera_name=SILHOUETTE_SHAPE_CAMERA,
        )
        render_selected_from_sweep(
            sweep_dir=OUT,
            pick=args.pick,
            build_scene=build_silhouette_shape_scene,
            root=ROOT,
            config=config,
            postprocess=None,
            title="Silhouette Shape Selected Render",
            notes=[
                "Promoted after a blind silhouette pass.",
                "Use this larger render to confirm the outline before material or lighting polish.",
            ],
        )
        return

    blind_tile = TILE_PRESETS["auto_tiny_grid"].without_labels()
    labeled_tile = TILE_PRESETS["auto_tiny_grid"]
    config = replace(
        RENDER_PRESETS["shape_scout"],
        resolution_x=420,
        resolution_y=300,
        samples=1,
        camera_name=SILHOUETTE_SHAPE_CAMERA,
        tile=labeled_tile if args.labels else blind_tile,
    )
    out_dir = OUT / "labeled" if args.labels else OUT
    render_sweep(
        variants=variants,
        build_scene=build_silhouette_shape_scene,
        out_dir=out_dir,
        root=ROOT,
        config=config,
        postprocess=None,
        title="Silhouette Shape Scout" if not args.labels else "Silhouette Shape Scout Labeled Rerun",
        notes=[
            "Blind first pass: judge outline at thumbnail scale before reading labels.",
            "Use `metadata.json` or the generated README for pick handles after the visual choice.",
            "Rerun with `--labels` or promote one pick with `--pick` before material polish.",
        ],
        promotion_command="/Applications/Blender.app/Contents/MacOS/Blender --background --python examples/silhouette_shape_scout.py -- --pick {pick}",
        square=True,
    )


if __name__ == "__main__":
    main()
