from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from blender_workbench.presets import RENDER_PRESETS, TILE_PRESETS
from blender_workbench.recipes.subsurface import SUBSURFACE_CAMERA, build_subsurface_scene, subsurface_variants
from blender_workbench.sweep import render_sweep


OUT = ROOT / "examples" / "output" / "subsurface_scout"


def main() -> None:
    config = replace(
        RENDER_PRESETS["cycles_preview"],
        resolution_x=520,
        resolution_y=360,
        samples=24,
        max_bounces=8,
        camera_name=SUBSURFACE_CAMERA,
        tile=TILE_PRESETS["auto_tiny_grid"],
    )
    render_sweep(
        variants=subsurface_variants(),
        build_scene=build_subsurface_scene,
        out_dir=OUT,
        root=ROOT,
        config=config,
        postprocess=None,
        title="Subsurface Scout",
        notes=[
            "Dense material board for subsurface color, radius, thickness, roughness, and backlight.",
            "Inspired by the local BlenderArt lighting/material resources.",
        ],
        square=True,
    )


if __name__ == "__main__":
    main()
