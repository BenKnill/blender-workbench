from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from blender_workbench.presets import RENDER_PRESETS, TILE_PRESETS
from blender_workbench.recipes.rocket_plume import ROCKET_PLUME_CAMERA, build_rocket_plume_scene, rocket_plume_texture_variants
from blender_workbench.sweep import render_sweep


OUT = ROOT / "examples" / "output" / "rocket_plume_texture_scout"


def main() -> None:
    config = replace(
        RENDER_PRESETS["cycles_preview"],
        resolution_x=560,
        resolution_y=360,
        samples=16,
        camera_name=ROCKET_PLUME_CAMERA,
        tile=TILE_PRESETS["auto_tiny_grid"],
    )
    render_sweep(
        variants=rocket_plume_texture_variants(),
        build_scene=build_rocket_plume_scene,
        out_dir=OUT,
        root=ROOT,
        config=config,
        title="Rocket Vacuum Plume Texture Scout",
        notes=[
            "Named stride scout for spatial density texture: ribbons, wisps, clumps, and filament wiggle.",
            "Overdone is now an aesthetic target; whiteout_fail is the true too-far anchor.",
        ],
        square=True,
    )


if __name__ == "__main__":
    main()
