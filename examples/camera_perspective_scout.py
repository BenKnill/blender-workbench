from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from blender_workbench.presets import RENDER_PRESETS, TILE_PRESETS
from blender_workbench.recipes.camera_perspective import (
    CAMERA_PERSPECTIVE_CAMERA,
    build_camera_perspective_scene,
    camera_perspective_variants,
)
from blender_workbench.sweep import render_sweep


OUT = ROOT / "examples" / "output" / "camera_perspective_scout"


def main() -> None:
    config = replace(
        RENDER_PRESETS["cycles_preview"],
        resolution_x=540,
        resolution_y=360,
        samples=18,
        camera_name=CAMERA_PERSPECTIVE_CAMERA,
        tile=TILE_PRESETS["auto_tiny_grid"],
    )
    render_sweep(
        variants=camera_perspective_variants(),
        build_scene=build_camera_perspective_scene,
        out_dir=OUT,
        root=ROOT,
        config=config,
        postprocess=None,
        title="Camera Perspective Scout",
        notes=[
            "5x5 same-view stride sheet: lens, foreground anchors, background anchors, grid depth, and subject depth.",
            "Increase lens_stride, foreground_stride, background_stride, grid_stride, or subject_stride if the sheet looks timid.",
            "Inspired by BlenderArt pack-shot and virtual-set camera setup lessons.",
        ],
        square=True,
    )


if __name__ == "__main__":
    main()
