from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from blender_workbench.presets import RENDER_PRESETS, TILE_PRESETS
from blender_workbench.recipes.rocket_plume import ROCKET_PLUME_CAMERA, build_rocket_plume_scene, rocket_plume_texture_variants
from blender_workbench.sweep import SweepVariant, render_sweep


OUT = ROOT / "examples" / "output" / "mini_plume_sweep"
MINI_PLUME_LABELS = ("grain_wide", "billowy", "wispy", "whiteout_fail")


def mini_plume_variants() -> list[SweepVariant]:
    """Curate a compact board from the richer rocket-plume texture workflow."""

    variants_by_label = {variant.label: variant for variant in rocket_plume_texture_variants(prefix="mini")}
    return [variants_by_label[label] for label in MINI_PLUME_LABELS]


VARIANTS = mini_plume_variants()


def main() -> None:
    config = replace(RENDER_PRESETS["cycles_preview"], camera_name=ROCKET_PLUME_CAMERA, tile=TILE_PRESETS["hero_pair"])
    render_sweep(
        variants=VARIANTS,
        build_scene=build_rocket_plume_scene,
        out_dir=OUT,
        root=ROOT,
        config=config,
        title="Mini Vacuum Plume Sweep",
        notes=["Compact default plume board using the richer recipe-backed texture workflow."],
    )


if __name__ == "__main__":
    main()
