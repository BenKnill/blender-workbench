from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from blender_workbench.materials import principled_material, transparent_emission_material
from blender_workbench.sweep import RenderConfig, SweepVariant, TileSpec, render_sweep


OUT = ROOT / "examples" / "output" / "mini_plume_sweep"


def clear_scene() -> None:
    import bpy

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def look_at(obj, target) -> None:
    from mathutils import Vector

    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def open_cone(name: str, start, end, r1: float, r2: float, mat) -> None:
    import bpy
    from mathutils import Vector

    start_v = Vector(start)
    end_v = Vector(end)
    mid = (start_v + end_v) * 0.5
    bpy.ops.mesh.primitive_cone_add(vertices=64, radius1=r1, radius2=r2, depth=(end_v - start_v).length, end_fill_type="NOTHING", location=mid)
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    obj.rotation_euler = (end_v - start_v).to_track_quat("Z", "Y").to_euler()


def build_scene(settings: dict) -> None:
    import bpy

    clear_scene()
    world = bpy.context.scene.world or bpy.data.worlds.new("mini plume world")
    bpy.context.scene.world = world
    world.color = (0.0, 0.0, 0.0)

    body = principled_material("stage white", (0.65, 0.68, 0.68, 1), roughness=0.7)
    nozzle = principled_material("dark nozzle", (0.03, 0.03, 0.035, 1), roughness=0.5, metallic=0.3)
    shell = transparent_emission_material("plume shell", (0.52, 0.66, 0.82, 1), settings["shell_strength"], settings["shell_alpha"])
    filament = transparent_emission_material("edge filaments", (0.48, 0.72, 1.0, 1), settings["filament_strength"], settings["filament_alpha"])

    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=0.28, depth=2.4, location=(-1.2, 0, 0), rotation=(0, math.pi / 2, 0))
    bpy.context.object.data.materials.append(body)
    bpy.ops.mesh.primitive_cone_add(vertices=48, radius1=0.25, radius2=0.08, depth=0.55, location=(0.1, 0, 0), rotation=(0, math.pi / 2, 0))
    bpy.context.object.data.materials.append(nozzle)

    open_cone("open translucent plume shell", (0.25, 0, 0), (4.7 * settings["length"], 0, 0), 0.12, 1.8 * settings["width"], shell)
    for i in range(settings["filament_count"]):
        y = math.sin(i * 2.1) * (0.2 + i / settings["filament_count"] * 1.3)
        z = math.cos(i * 1.7) * (0.1 + i / settings["filament_count"] * 0.8)
        open_cone(f"filament {i:02d}", (0.22, 0, 0), (4.0, y, z), 0.005, 0.014, filament)

    bpy.ops.object.light_add(type="SUN", location=(-3, -4, 3))
    bpy.context.object.data.energy = 1.8
    bpy.ops.object.camera_add(location=(2.4, -6.0, 1.0))
    cam = bpy.context.object
    cam.name = "camera_profile"
    look_at(cam, (2.4, 0, 0))
    bpy.context.scene.camera = cam


VARIANTS = [
    SweepVariant("thin_shell", {"shell_alpha": 0.04, "shell_strength": 0.55, "filament_alpha": 0.14, "filament_strength": 0.8, "filament_count": 20, "width": 1.0, "length": 1.0}),
    SweepVariant("wide_shell", {"shell_alpha": 0.03, "shell_strength": 0.50, "filament_alpha": 0.10, "filament_strength": 0.7, "filament_count": 18, "width": 1.35, "length": 0.9}),
    SweepVariant("filament_heavy", {"shell_alpha": 0.015, "shell_strength": 0.38, "filament_alpha": 0.28, "filament_strength": 1.0, "filament_count": 42, "width": 1.0, "length": 1.0}),
    SweepVariant("opaque_failure", {"shell_alpha": 0.18, "shell_strength": 0.75, "filament_alpha": 0.08, "filament_strength": 0.5, "filament_count": 10, "width": 1.0, "length": 1.0}, note="failure anchor: too solid"),
]


def main() -> None:
    render_sweep(
        variants=VARIANTS,
        build_scene=build_scene,
        out_dir=OUT,
        root=ROOT,
        config=RenderConfig(resolution_x=760, resolution_y=500, samples=48, camera_name="camera_profile", tile=TileSpec(width=320, height=210, columns=2)),
        title="Mini Vacuum Plume Sweep",
        notes=["Small example for the workbench API; use it as a pattern, not a finished visual."],
    )


if __name__ == "__main__":
    main()

