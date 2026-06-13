from __future__ import annotations

import dataclasses
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from blender_workbench.materials import principled_material
from blender_workbench.sweep import SweepVariant, named_variants


SUBSURFACE_CAMERA = "subsurface_camera"


@dataclass(frozen=True)
class SubsurfaceSettings:
    color: tuple[float, float, float, float] = (1.0, 0.58, 0.32, 1.0)
    subsurface_weight: float = 0.38
    subsurface_radius: tuple[float, float, float] = (1.0, 0.36, 0.12)
    subsurface_scale: float = 0.8
    transmission_weight: float = 0.0
    roughness: float = 0.42
    subject_scale: tuple[float, float, float] = (0.72, 0.72, 0.78)
    key_light_energy: float = 260.0
    back_light_energy: float = 620.0
    core_light_energy: float = 35.0
    light_size: float = 2.0
    surface_bump_strength: float = 0.0
    surface_bump_scale: float = 18.0
    floor_color: tuple[float, float, float, float] = (0.20, 0.18, 0.21, 1.0)
    wall_color: tuple[float, float, float, float] = (0.11, 0.12, 0.18, 1.0)


def coerce_subsurface_settings(settings: SubsurfaceSettings | Mapping[str, Any] | None = None) -> SubsurfaceSettings:
    if isinstance(settings, SubsurfaceSettings):
        return settings
    data = dataclasses.asdict(SubsurfaceSettings())
    if settings:
        data.update({key: value for key, value in dict(settings).items() if key in data})
    return SubsurfaceSettings(**data)


def subsurface_variants(*, prefix: str = "sss") -> list[SweepVariant]:
    return named_variants(
        {
            "matte_fail": {
                "color": (0.72, 0.58, 0.50, 1.0),
                "subsurface_weight": 0.0,
                "subsurface_scale": 0.0,
                "back_light_energy": 360.0,
                "core_light_energy": 0.0,
                "roughness": 0.78,
            },
            "low_wax": {"subsurface_weight": 0.18, "subsurface_scale": 0.42, "back_light_energy": 520.0},
            "deep_wax": {"subsurface_weight": 0.48, "subsurface_scale": 1.3, "core_light_energy": 45.0},
            "opal": {
                "color": (0.82, 0.95, 1.0, 1.0),
                "subsurface_weight": 0.46,
                "subsurface_radius": (0.62, 0.86, 1.0),
                "subsurface_scale": 1.0,
                "core_light_energy": 42.0,
            },
            "amber": {
                "color": (1.0, 0.48, 0.16, 1.0),
                "subsurface_weight": 0.56,
                "subsurface_radius": (1.0, 0.38, 0.10),
                "subsurface_scale": 0.95,
                "core_light_energy": 58.0,
            },
            "ruby": {
                "color": (0.95, 0.10, 0.08, 1.0),
                "subsurface_weight": 0.68,
                "subsurface_radius": (1.0, 0.16, 0.06),
                "subsurface_scale": 1.1,
                "core_light_energy": 78.0,
            },
            "blue_jelly": {
                "color": (0.24, 0.55, 1.0, 1.0),
                "subsurface_weight": 0.42,
                "subsurface_radius": (0.18, 0.45, 1.0),
                "subsurface_scale": 1.25,
                "transmission_weight": 0.18,
                "roughness": 0.18,
            },
            "green_jelly": {
                "color": (0.28, 0.96, 0.54, 1.0),
                "subsurface_weight": 0.40,
                "subsurface_radius": (0.20, 1.0, 0.36),
                "subsurface_scale": 1.1,
                "transmission_weight": 0.14,
                "roughness": 0.20,
            },
            "milk": {
                "color": (0.96, 0.92, 0.84, 1.0),
                "subsurface_weight": 0.76,
                "subsurface_radius": (1.0, 0.82, 0.54),
                "subsurface_scale": 0.75,
                "roughness": 0.66,
            },
            "thin": {"subject_scale": (0.54, 0.54, 0.56), "subsurface_scale": 0.45, "core_light_energy": 25.0},
            "thick": {"subject_scale": (0.84, 0.84, 0.98), "subsurface_scale": 1.5, "core_light_energy": 52.0},
            "backlit": {"back_light_energy": 980.0, "key_light_energy": 120.0, "light_size": 1.1},
            "core_glow": {"core_light_energy": 145.0, "back_light_energy": 420.0},
            "rough_skin": {"surface_bump_strength": 0.11, "surface_bump_scale": 42.0, "roughness": 0.84},
            "soft_light": {"light_size": 4.4, "back_light_energy": 760.0, "key_light_energy": 360.0},
            "overdone": {
                "subsurface_weight": 0.95,
                "subsurface_scale": 2.6,
                "transmission_weight": 0.26,
                "core_light_energy": 210.0,
                "back_light_energy": 1150.0,
                "roughness": 0.12,
            },
        },
        prefix=prefix,
        note="subsurface color, radius, thickness, and backlight scout",
    )


def clear_scene() -> None:
    import bpy

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def look_at(obj: Any, target: tuple[float, float, float]) -> None:
    from mathutils import Vector

    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def _apply_noise_bump(mat: Any, settings: SubsurfaceSettings) -> None:
    if settings.surface_bump_strength <= 0:
        return
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    if not bsdf or "Normal" not in bsdf.inputs:
        return
    noise = nodes.new(type="ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = settings.surface_bump_scale
    noise.inputs["Detail"].default_value = 10.0
    noise.inputs["Roughness"].default_value = 0.58
    bump = nodes.new(type="ShaderNodeBump")
    bump.inputs["Strength"].default_value = settings.surface_bump_strength
    bump.inputs["Distance"].default_value = 0.075
    links.new(noise.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])


def _material(settings: SubsurfaceSettings) -> Any:
    mat = principled_material(
        "subsurface study material",
        settings.color,
        roughness=settings.roughness,
        subsurface_weight=settings.subsurface_weight,
        subsurface_radius=settings.subsurface_radius,
        subsurface_scale=settings.subsurface_scale,
        transmission_weight=settings.transmission_weight,
    )
    _apply_noise_bump(mat, settings)
    return mat


def _add_set(settings: SubsurfaceSettings) -> None:
    import bpy

    floor = principled_material("sss floor", settings.floor_color, roughness=0.86)
    wall = principled_material("sss wall", settings.wall_color, roughness=0.9)

    bpy.ops.mesh.primitive_plane_add(size=4.6, location=(0, 0.05, 0))
    floor_obj = bpy.context.object
    floor_obj.name = "matte subsurface floor"
    floor_obj.data.materials.append(floor)

    bpy.ops.mesh.primitive_plane_add(size=4.6, location=(0, 1.85, 1.7), rotation=(math.pi / 2, 0, 0))
    wall_obj = bpy.context.object
    wall_obj.name = "dark subsurface wall"
    wall_obj.data.materials.append(wall)


def _shade_smooth(obj: Any) -> None:
    import bpy

    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.shade_smooth()
    obj.select_set(False)


def _add_subject(settings: SubsurfaceSettings) -> None:
    import bpy

    mat = _material(settings)

    bpy.ops.mesh.primitive_uv_sphere_add(segments=40, ring_count=20, radius=0.72, location=(0.02, 0.38, 0.78))
    body = bpy.context.object
    body.name = "subsurface main blob"
    body.scale = settings.subject_scale
    body.data.materials.append(mat)
    _shade_smooth(body)

    bpy.ops.mesh.primitive_uv_sphere_add(segments=28, ring_count=14, radius=0.28, location=(-0.78, 0.28, 0.42))
    bead = bpy.context.object
    bead.name = "thin reference bead"
    bead.scale = (0.72, 0.72, 0.38)
    bead.data.materials.append(mat)
    _shade_smooth(bead)

    bpy.ops.mesh.primitive_cube_add(size=1, location=(0.88, 0.26, 0.45), rotation=(0.0, 0.0, math.radians(-7.0)))
    slab = bpy.context.object
    slab.name = "rounded thickness slab"
    slab.scale = (0.13, 0.38, 0.42)
    slab.data.materials.append(mat)
    bevel = slab.modifiers.new("soft bevel", "BEVEL")
    bevel.width = 0.12
    bevel.segments = 8
    slab.modifiers.new("weighted normals", "WEIGHTED_NORMAL")


def _add_lights(settings: SubsurfaceSettings) -> None:
    import bpy

    bpy.ops.object.light_add(type="AREA", location=(-1.35, -2.0, 1.9))
    key = bpy.context.object
    key.name = "soft front key"
    key.data.energy = settings.key_light_energy
    key.data.size = settings.light_size * 0.75
    key.data.color = (1.0, 0.82, 0.62)
    look_at(key, (0.0, 0.35, 0.75))

    bpy.ops.object.light_add(type="AREA", location=(0.45, 1.32, 1.2))
    back = bpy.context.object
    back.name = "subsurface backlight"
    back.data.energy = settings.back_light_energy
    back.data.size = settings.light_size
    back.data.color = (1.0, 0.50, 0.28)
    look_at(back, (0.0, 0.34, 0.78))

    if settings.core_light_energy > 0:
        bpy.ops.object.light_add(type="POINT", location=(0.03, 0.36, 0.78))
        core = bpy.context.object
        core.name = "hidden warm core light"
        core.data.energy = settings.core_light_energy
        core.data.color = (1.0, 0.36, 0.16)
        core.data.shadow_soft_size = 0.85


def _add_camera() -> None:
    import bpy

    bpy.ops.object.camera_add(location=(0.18, -3.55, 1.23))
    cam = bpy.context.object
    cam.name = SUBSURFACE_CAMERA
    look_at(cam, (0.0, 0.36, 0.74))
    cam.data.lens = 50
    bpy.context.scene.camera = cam


def build_subsurface_scene(settings: SubsurfaceSettings | Mapping[str, Any] | None = None) -> None:
    import bpy

    subsurface_settings = coerce_subsurface_settings(settings)
    clear_scene()
    world = bpy.context.scene.world or bpy.data.worlds.new("subsurface world")
    bpy.context.scene.world = world
    world.color = (0.012, 0.014, 0.022)
    _add_set(subsurface_settings)
    _add_subject(subsurface_settings)
    _add_lights(subsurface_settings)
    _add_camera()
