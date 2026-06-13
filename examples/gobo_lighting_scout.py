from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from blender_workbench.presets import RENDER_PRESETS, TILE_PRESETS
from blender_workbench.recipes.gobo_lighting import GOBO_CAMERA, build_gobo_lighting_scene, gobo_lighting_variants
from blender_workbench.sweep import render_sweep


OUT = ROOT / "examples" / "output" / "gobo_lighting_scout"


def main() -> None:
    config = replace(
        RENDER_PRESETS["cycles_preview"],
        resolution_x=520,
        resolution_y=360,
        samples=18,
        camera_name=GOBO_CAMERA,
        tile=TILE_PRESETS["auto_tiny_grid"],
    )
    render_sweep(
        variants=gobo_lighting_variants(),
        build_scene=build_gobo_lighting_scene,
        out_dir=OUT,
        root=ROOT,
        config=config,
        postprocess=None,
        title="Gobo Lighting Scout",
        notes=[
            "Dense study board for projected shadow texture, gel color, light size, and blocker distance.",
            "Inspired by the local BlenderArt lighting and texturing resources.",
        ],
        square=True,
    )


if __name__ == "__main__":
    main()
