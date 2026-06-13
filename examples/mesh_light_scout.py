from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from blender_workbench.presets import RENDER_PRESETS, TILE_PRESETS
from blender_workbench.recipes.mesh_light import MESH_LIGHT_CAMERA, build_mesh_light_scene, mesh_light_variants
from blender_workbench.scene_sanity import SceneSanityExpectations, format_scene_sanity_report, run_scene_sanity
from blender_workbench.sweep import configure_render, render_profile_comparison_from_sweep, render_selected_from_sweep, render_sweep


OUT = ROOT / "examples" / "output" / "mesh_light_scout"
MESH_LIGHT_SCENE_EXPECTATIONS = SceneSanityExpectations(
    expected_camera=MESH_LIGHT_CAMERA,
    expected_objects=(
        "mesh light floor",
        "mesh light wall",
        "matte light read sphere",
        "emissive softbox mesh",
    ),
    expected_materials=(
        "visible emissive mesh light",
        "matte hero object",
        "mesh light floor",
        "mesh light wall",
    ),
    require_world=True,
    min_subject_objects=6,
)


def _script_args(argv: list[str] | None = None) -> list[str]:
    values = list(sys.argv[1:] if argv is None else argv)
    if "--" in values:
        return values[values.index("--") + 1 :]
    return values


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a mesh-light scout grid, or promote one picked tile.")
    parser.add_argument("--pick", help="variant name, label, or 1-based index to render with the hero profile")
    parser.add_argument("--compare-profiles", action="store_true", help="rerender the picked tile under preview and hero profiles")
    parser.add_argument("--check-scene", action="store_true", help="build one tile and print scene sanity warnings without rendering")
    parser.add_argument("--strict-scene", action="store_true", help="fail scene sanity warnings instead of recording them as non-fatal")
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
    config = replace(
        RENDER_PRESETS["cycles_preview"],
        resolution_x=540,
        resolution_y=360,
        samples=24,
        max_bounces=6,
        camera_name=MESH_LIGHT_CAMERA,
        tile=TILE_PRESETS["auto_tiny_grid"],
    )
    if args.check_scene:
        import bpy

        build_mesh_light_scene(variants[0].settings)
        configure_render(config)
        bpy.context.scene.camera = bpy.data.objects[MESH_LIGHT_CAMERA]
        report = run_scene_sanity(
            bpy.context.scene,
            config=config,
            expectations=MESH_LIGHT_SCENE_EXPECTATIONS,
            strict=args.strict_scene,
            output_dir=OUT,
        )
        print(format_scene_sanity_report(report))
        if not report.passed:
            raise SystemExit(2)
        return
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
        scene_expectations=MESH_LIGHT_SCENE_EXPECTATIONS,
        strict_scene_sanity=args.strict_scene,
        square=True,
    )


if __name__ == "__main__":
    main()
