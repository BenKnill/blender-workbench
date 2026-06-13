from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from blender_workbench.presets import RENDER_PRESETS, TILE_PRESETS
from blender_workbench.recipes.soft_atmosphere import SOFT_ATMOSPHERE_CAMERA, build_soft_atmosphere_scene, soft_atmosphere_variants
from blender_workbench.sweep import render_sweep


OUT = ROOT / "examples" / "output" / "soft_atmosphere_scout"


def main() -> None:
    config = replace(
        RENDER_PRESETS["cycles_preview"],
        resolution_x=500,
        resolution_y=330,
        samples=18,
        max_bounces=4,
        camera_name=SOFT_ATMOSPHERE_CAMERA,
        tile=TILE_PRESETS["auto_tiny_grid"],
    )
    render_sweep(
        variants=soft_atmosphere_variants(),
        build_scene=build_soft_atmosphere_scene,
        out_dir=OUT,
        root=ROOT,
        config=config,
        postprocess=None,
        title="Soft Atmosphere Card Scout",
        notes=[
            "Diagnostic board for soft-gradient card hardness, falloff width, alpha, glow strength, noise, and warmth.",
            "Use before placing horizon glow, haze sheets, or stylized light cards into selected renders.",
        ],
        square=True,
    )


if __name__ == "__main__":
    main()
