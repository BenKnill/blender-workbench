from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from blender_workbench.presets import RENDER_PRESETS, TILE_PRESETS
from blender_workbench.recipes.transparency import TRANSPARENCY_CAMERA, build_transparency_scene, transparency_variants
from blender_workbench.sweep import render_sweep


OUT = ROOT / "examples" / "output" / "transparency_scout"


def main() -> None:
    config = replace(
        RENDER_PRESETS["cycles_preview"],
        resolution_x=540,
        resolution_y=360,
        samples=24,
        max_bounces=8,
        transparent_max_bounces=32,
        camera_name=TRANSPARENCY_CAMERA,
        tile=TILE_PRESETS["auto_tiny_grid"],
    )
    render_sweep(
        variants=transparency_variants(),
        build_scene=build_transparency_scene,
        out_dir=OUT,
        root=ROOT,
        config=config,
        postprocess=None,
        title="Transparency Scout",
        notes=[
            "5x5 stride sheet: alpha, roughness, IOR, pane thickness, and tint.",
            "Increase alpha_stride, roughness_stride, ior_stride, thickness_stride, or tint_stride if the sheet looks timid.",
            "Inspired by BlenderArt glass, alpha, Fresnel, and glowing-bulb material notes.",
        ],
        square=True,
    )


if __name__ == "__main__":
    main()
