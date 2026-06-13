from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from blender_workbench.presets import RENDER_PRESETS, TILE_PRESETS
from blender_workbench.recipes.mesh_light import MESH_LIGHT_CAMERA, build_mesh_light_scene, mesh_light_variants
from blender_workbench.sweep import render_profile_comparison_from_sweep, render_selected_from_sweep, render_sweep


OUT = ROOT / "examples" / "output" / "mesh_light_scout"


def _script_args(argv: list[str] | None = None) -> list[str]:
    values = list(sys.argv[1:] if argv is None else argv)
    if "--" in values:
        return values[values.index("--") + 1 :]
    return values


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a mesh-light scout grid, or promote one picked tile.")
    parser.add_argument("--pick", help="variant name, label, or 1-based index to render with the hero profile")
    parser.add_argument("--compare-profiles", action="store_true", help="rerender the picked tile under preview and hero profiles")
    parser.add_argument("--hero-samples", type=int, default=96, help="Cycles samples for --pick")
    parser.add_argument("--save-blend", action="store_true", help="also save a selected .blend for GUI review")
    parser.add_argument("--export-blend-only", action="store_true", help="save the selected .blend and skip image rendering")
    args, _unknown = parser.parse_known_args(_script_args(argv))
    return args


def _profile_comparison_configs(hero_samples: int):
    preview = replace(
        RENDER_PRESETS["cycles_preview"],
        resolution_x=540,
        resolution_y=360,
        samples=24,
        max_bounces=6,
        camera_name=MESH_LIGHT_CAMERA,
        tile=TILE_PRESETS["filmstrip"],
    )
    hero = replace(
        RENDER_PRESETS["hero_check"],
        samples=hero_samples,
        camera_name=MESH_LIGHT_CAMERA,
        tile=TILE_PRESETS["filmstrip"],
    )
    return (("cycles_preview", preview), ("hero_check", hero))


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    variants = mesh_light_variants()
    if args.compare_profiles:
        render_profile_comparison_from_sweep(
            sweep_dir=OUT,
            pick=args.pick,
            build_scene=build_mesh_light_scene,
            root=ROOT,
            profiles=_profile_comparison_configs(args.hero_samples),
            postprocess=None,
            title="Mesh Light Profile Comparison",
            notes=[
                "Checks whether the selected mesh-light tile survives the jump from scout preview to hero render.",
                "Look for shadow softness, noise, emissive falloff, and subject-read drift before promotion.",
            ],
            source_sweep_dir=OUT,
        )
        return
    if args.pick:
        config = replace(
            RENDER_PRESETS["hero_check"],
            samples=args.hero_samples,
            camera_name=MESH_LIGHT_CAMERA,
        )
        render_selected_from_sweep(
            sweep_dir=OUT,
            pick=args.pick,
            build_scene=build_mesh_light_scene,
            root=ROOT,
            config=config,
            postprocess=None,
            title="Mesh Light Selected Render",
            notes=[
                "Promoted after inspecting the mesh-light contact sheet.",
                "Use this heavier render to judge noise, shadow softness, and subject read.",
            ],
            source_sweep_dir=OUT,
            save_blend=args.save_blend or args.export_blend_only,
            render_image=not args.export_blend_only,
        )
        return

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
        variants=variants,
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
        promotion_command="/Applications/Blender.app/Contents/MacOS/Blender --background --python examples/mesh_light_scout.py -- --pick {pick}",
        profile_comparison_command="/Applications/Blender.app/Contents/MacOS/Blender --background --python examples/mesh_light_scout.py -- --pick {pick} --compare-profiles",
        square=True,
    )


if __name__ == "__main__":
    main()
