from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from blender_workbench.presets import RENDER_PRESETS, TILE_PRESETS
from blender_workbench.recipes.mesh_light import MESH_LIGHT_CAMERA, build_mesh_light_scene, mesh_light_variants
from blender_workbench.sweep import render_sweep


OUT = ROOT / "examples" / "output" / "mesh_light_scout"


def main() -> None:
    config = replace(
        RENDER_PRESETS["cycles_preview"],
        resolution_x=540,
        resolution_y=360,
        samples=24,
        max_bounces=6,
        camera_name=MESH_LIGHT_CAMERA,
        tile=TILE_PRESETS["auto_tiny_grid"],
    )
    render_sweep(
        variants=mesh_light_variants(),
        build_scene=build_mesh_light_scene,
        out_dir=OUT,
        root=ROOT,
        config=config,
        postprocess=None,
        title="Mesh Light Scout",
        notes=[
            "5x5 same-view stride sheet: emissive mesh size, distance, height, fill, and gel/shape.",
            "Inspired by BlenderArt mesh-light and studio pack-shot lessons.",
        ],
        square=True,
    )


if __name__ == "__main__":
    main()
