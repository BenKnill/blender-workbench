from __future__ import annotations

import argparse
import math
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from blender_workbench.camera import add_orbit_camera, look_at
from blender_workbench.materials import emission_material, principled_material, transparent_emission_material
from blender_workbench.presets import RENDER_PRESETS, TILE_PRESETS
from blender_workbench.render_passes import render_pass_diagnostic_sheet


OUT = ROOT / "examples" / "output" / "render_pass_diagnostic_scout"
CAMERA = "render_pass_diagnostic_camera"


def _script_args(argv: list[str] | None = None) -> list[str]:
    values = list(sys.argv[1:] if argv is None else argv)
    if "--" in values:
        return values[values.index("--") + 1 :]
    return values


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a fixed-scene contact sheet of render-pass diagnostics.")
    parser.add_argument("--samples", type=int, default=24, help="Cycles samples for the diagnostic render")
    args, _unknown = parser.parse_known_args(_script_args(argv))
    return args


def clear_scene() -> None:
    import bpy

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def _shade_smooth(obj) -> None:
    import bpy

    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.shade_smooth()
    obj.select_set(False)


def _cube(name: str, location, scale, mat) -> None:
    import bpy

    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(mat)


def build_pass_diagnostic_scene(_settings=None) -> None:
    import bpy

    clear_scene()
    world = bpy.context.scene.world or bpy.data.worlds.new("render pass diagnostic world")
    bpy.context.scene.world = world
    world.color = (0.018, 0.020, 0.026)

    floor_mat = principled_material("pass floor clay", (0.28, 0.26, 0.23, 1.0), roughness=0.82)
    wall_mat = principled_material("pass matte wall", (0.12, 0.14, 0.18, 1.0), roughness=0.9)
    sphere_mat = principled_material("pass glossy subject", (0.76, 0.52, 0.34, 1.0), roughness=0.32, metallic=0.0)
    dark_mat = principled_material("pass dark occluder", (0.055, 0.058, 0.065, 1.0), roughness=0.74)
    glow_mat = emission_material("pass warm emission strip", (1.0, 0.42, 0.16, 1.0), 1.6)
    alpha_mat = transparent_emission_material("pass alpha card", (0.45, 0.74, 1.0, 1.0), strength=0.2, alpha=0.28)

    bpy.ops.mesh.primitive_plane_add(size=5.0, location=(0, 0.16, 0))
    floor = bpy.context.object
    floor.name = "pass diagnostic floor"
    floor.data.materials.append(floor_mat)

    bpy.ops.mesh.primitive_plane_add(size=5.0, location=(0, 1.92, 1.72), rotation=(math.pi / 2, 0, 0))
    wall = bpy.context.object
    wall.name = "pass diagnostic wall"
    wall.data.materials.append(wall_mat)

    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=0.68, location=(-0.30, 0.36, 0.78))
    sphere = bpy.context.object
    sphere.name = "pass glossy sphere"
    sphere.scale = (1.0, 0.92, 0.82)
    sphere.data.materials.append(sphere_mat)
    _shade_smooth(sphere)

    _cube("pass hard shadow block", (0.82, 0.20, 0.46), (0.28, 0.34, 0.46), dark_mat)
    _cube("pass emission strip", (-1.14, 1.82, 1.12), (0.10, 0.020, 0.74), glow_mat)
    _cube("pass transparent card", (0.30, -0.10, 0.86), (0.06, 0.020, 0.58), alpha_mat)

    bpy.ops.object.light_add(type="AREA", location=(-1.8, -2.1, 2.5))
    key = bpy.context.object
    key.name = "pass broad key"
    key.data.energy = 420
    key.data.size = 2.6
    key.data.color = (1.0, 0.86, 0.70)
    look_at(key, (0.0, 0.24, 0.75))

    bpy.ops.object.light_add(type="POINT", location=(1.55, 1.10, 1.3))
    rim = bpy.context.object
    rim.name = "pass small rim"
    rim.data.energy = 95
    rim.data.color = (0.56, 0.72, 1.0)
    rim.data.shadow_soft_size = 0.55

    add_orbit_camera(
        name=CAMERA,
        target=(0.08, 0.28, 0.76),
        distance=3.85,
        lens_mm=58.0,
        yaw_degrees=-2.0,
        pitch_degrees=10.0,
    )


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    config = replace(
        RENDER_PRESETS["cycles_preview"],
        resolution_x=640,
        resolution_y=440,
        samples=args.samples,
        camera_name=CAMERA,
        tile=TILE_PRESETS["filmstrip"],
    )
    render_pass_diagnostic_sheet(
        build_scene=build_pass_diagnostic_scene,
        out_dir=OUT,
        root=ROOT,
        config=config,
        title="Render Pass Diagnostic Scout",
        notes=[
            "Inspect pass contributions before running compositor or final-look sweeps.",
            "Unavailable pass outputs are recorded as warnings instead of failing the workflow.",
        ],
        tile=TILE_PRESETS["filmstrip"],
    )


if __name__ == "__main__":
    main()
