from __future__ import annotations

import math
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from blender_workbench.presets import RENDER_PRESETS, TILE_PRESETS
from blender_workbench.sweep import named_variants, render_sweep


OUT = ROOT / "examples" / "output" / "light_texture_scout"


CASES = named_variants(
    {
        "locked_clean": {
            "light_jitter_radius": 0.0,
            "light_jitter_count": 1,
            "texture_magnitude": 0.0,
            "noise_scale": 16.0,
            "surface_bump_strength": 0.0,
        },
        "locked_grain": {
            "light_jitter_radius": 0.0,
            "light_jitter_count": 1,
            "texture_magnitude": 0.45,
            "noise_scale": 80.0,
            "surface_bump_strength": 0.08,
        },
        "hand_grain": {
            "light_jitter_radius": 0.18,
            "light_jitter_count": 3,
            "texture_magnitude": 0.45,
            "noise_scale": 80.0,
            "surface_bump_strength": 0.08,
        },
        "hand_rugged": {
            "light_jitter_radius": 0.18,
            "light_jitter_count": 3,
            "texture_magnitude": 1.1,
            "noise_scale": 16.0,
            "surface_bump_strength": 0.24,
        },
        "restless_rugged": {
            "light_jitter_radius": 0.42,
            "light_jitter_count": 5,
            "texture_magnitude": 1.1,
            "noise_scale": 16.0,
            "surface_bump_strength": 0.24,
        },
        "broad_lumpy": {
            "light_jitter_radius": 0.3,
            "light_jitter_count": 4,
            "texture_magnitude": 1.35,
            "noise_scale": 3.2,
            "surface_bump_strength": 0.30,
        },
        "overdone_fail": {
            "light_jitter_radius": 0.5,
            "light_jitter_count": 6,
            "texture_magnitude": 1.9,
            "noise_scale": 28.0,
            "surface_bump_strength": 0.42,
        },
    },
    note="named light jitter and texture magnitude scout",
)


def clear_scene() -> None:
    import bpy

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def look_at(obj, target) -> None:
    from mathutils import Vector

    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def textured_material(settings: dict):
    import bpy

    mat = bpy.data.materials.new("scout textured clay")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if not bsdf:
        return mat

    strength = settings["texture_magnitude"]
    bsdf.inputs["Roughness"].default_value = 0.72

    noise = mat.node_tree.nodes.new(type="ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = settings["noise_scale"]
    noise.inputs["Detail"].default_value = 13.0
    noise.inputs["Roughness"].default_value = 0.64

    ramp = mat.node_tree.nodes.new(type="ShaderNodeValToRGB")
    low = max(0.02, 0.48 - strength * 0.34)
    high = min(1.0, 0.56 + strength * 0.32)
    ramp.color_ramp.elements[0].position = max(0.0, 0.42 - strength * 0.08)
    ramp.color_ramp.elements[0].color = (low * 0.82, low * 0.94, low, 1.0)
    ramp.color_ramp.elements[1].position = min(1.0, 0.58 + strength * 0.08)
    ramp.color_ramp.elements[1].color = (high, high * 0.94, high * 0.84, 1.0)

    bump = mat.node_tree.nodes.new(type="ShaderNodeBump")
    bump.inputs["Strength"].default_value = settings["surface_bump_strength"]
    bump.inputs["Distance"].default_value = 0.26
    mat.node_tree.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    mat.node_tree.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    mat.node_tree.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    mat.node_tree.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def add_jittered_lights(settings: dict) -> None:
    import bpy

    count = max(1, int(settings["light_jitter_count"]))
    radius = float(settings["light_jitter_radius"])
    for index in range(count):
        angle = index * 2.399
        offset = radius * (0.45 + 0.55 * ((index % 3) / 2))
        x = -3.2 + math.cos(angle) * offset
        y = -4.0 + math.sin(angle) * offset
        z = 2.6 + math.sin(angle * 0.7) * offset * 0.5
        bpy.ops.object.light_add(type="AREA", location=(x, y, z))
        light = bpy.context.object
        light.name = f"jitter light {index:02d}"
        light.data.size = 1.3 + radius * 1.8
        light.data.energy = 260 / count * (1.0 + 0.12 * math.sin(index * 1.7))


def build_scene(settings: dict) -> None:
    import bpy

    clear_scene()
    world = bpy.context.scene.world or bpy.data.worlds.new("light texture scout world")
    bpy.context.scene.world = world
    world.color = (0.018, 0.02, 0.024)

    mat = textured_material(settings)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=1.0, location=(0, 0, 0.9))
    sphere = bpy.context.object
    sphere.name = "texture scout sphere"
    sphere.scale = (1.0, 1.0, 0.78)
    sphere.data.materials.append(mat)
    bpy.ops.object.shade_smooth()

    floor_mat = bpy.data.materials.new("matte floor")
    floor_mat.diffuse_color = (0.05, 0.055, 0.06, 1.0)
    bpy.ops.mesh.primitive_plane_add(size=4.5, location=(0, 0, -0.02))
    floor = bpy.context.object
    floor.name = "matte floor"
    floor.data.materials.append(floor_mat)

    add_jittered_lights(settings)

    bpy.ops.object.camera_add(location=(0.15, -4.2, 1.45))
    cam = bpy.context.object
    cam.name = "light_texture_camera"
    look_at(cam, (0.0, 0.0, 0.72))
    cam.data.lens = 56
    bpy.context.scene.camera = cam


def main() -> None:
    config = replace(
        RENDER_PRESETS["material_scout"],
        camera_name="light_texture_camera",
        tile=TILE_PRESETS["auto_square_moodboard"],
    )
    render_sweep(
        variants=CASES,
        build_scene=build_scene,
        out_dir=OUT,
        root=ROOT,
        config=config,
        postprocess=None,
        title="Light And Texture Scout",
        notes=["Named case board for light-source jitter and texture magnitude."],
        square=True,
    )


if __name__ == "__main__":
    main()
