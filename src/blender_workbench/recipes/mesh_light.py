from __future__ import annotations

import dataclasses
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from blender_workbench.camera import add_orbit_camera, look_at
from blender_workbench.materials import emission_material, principled_material
from blender_workbench.sweep import SweepVariant


MESH_LIGHT_CAMERA = "mesh_light_camera"


@dataclass(frozen=True)
class MeshLightSettings:
    panel_width: float = 1.25
    panel_height: float = 0.72
    panel_depth: float = 0.035
    panel_x: float = -1.15
    panel_y: float = -1.35
    panel_z: float = 2.05
    panel_strength: float = 18.0
    panel_color: tuple[float, float, float, float] = (1.0, 0.76, 0.46, 1.0)
    panel_twist: float = 0.0
    fill_strength: float = 34.0
    room_warmth: float = 0.35
    subject_roughness: float = 0.48
    shadow_blocker_scale: float = 1.0


def coerce_mesh_light_settings(settings: MeshLightSettings | Mapping[str, Any] | None = None) -> MeshLightSettings:
    if isinstance(settings, MeshLightSettings):
        return settings
    data = dataclasses.asdict(MeshLightSettings())
    if settings:
        data.update({key: value for key, value in dict(settings).items() if key in data})
    return MeshLightSettings(**data)


def _step_label(step: int) -> str:
    return "base" if step == 0 else f"{'p' if step > 0 else 'm'}{abs(step)}"


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _mix(a: tuple[float, float, float, float], b: tuple[float, float, float, float], amount: float) -> tuple[float, float, float, float]:
    return (
        a[0] * (1.0 - amount) + b[0] * amount,
        a[1] * (1.0 - amount) + b[1] * amount,
        a[2] * (1.0 - amount) + b[2] * amount,
        1.0,
    )


def mesh_light_variants(
    *,
    prefix: str = "mesh",
    steps: tuple[int, ...] = (-2, -1, 0, 1, 2),
    size_stride: float = 0.48,
    distance_stride: float = 0.42,
    height_stride: float = 0.42,
    fill_stride: float = 28.0,
) -> list[SweepVariant]:
    """Build a same-view stride board for emissive mesh lighting."""
    base = dataclasses.asdict(MeshLightSettings())
    variants: list[SweepVariant] = []

    def add(label: str, settings: Mapping[str, Any]) -> None:
        data = dict(base)
        data.update(settings)
        name = f"{prefix}_{label}" if prefix else label
        variants.append(
            SweepVariant(
                name=name,
                label=label,
                settings=data,
                note="same-view mesh-light scout: size, distance, height, fill, color/shape",
            )
        )

    for step in steps:
        size = _clamp(1.0 + step * size_stride, 0.18, 2.35)
        add(
            f"size_{_step_label(step)}",
            {
                "panel_width": 1.25 * size,
                "panel_height": 0.72 * size,
                "panel_strength": _clamp(18.0 / max(0.42, math.sqrt(size)), 7.0, 38.0),
            },
        )

    for step in steps:
        depth = _clamp(1.0 + step * distance_stride, 0.25, 2.1)
        add(
            f"dist_{_step_label(step)}",
            {
                "panel_y": -0.62 - depth * 0.95,
                "panel_x": -1.0 - step * 0.10,
                "panel_strength": _clamp(13.0 + depth * 7.5, 10.0, 36.0),
                "shadow_blocker_scale": _clamp(1.15 - step * 0.10, 0.72, 1.42),
            },
        )

    for step in steps:
        height = _clamp(2.05 + step * height_stride, 0.82, 3.45)
        add(
            f"height_{_step_label(step)}",
            {
                "panel_z": height,
                "panel_twist": step * -6.0,
                "room_warmth": _clamp(0.35 + step * 0.08, 0.08, 0.68),
            },
        )

    for step in steps:
        fill = _clamp(34.0 + step * fill_stride, 0.0, 125.0)
        add(
            f"fill_{_step_label(step)}",
            {
                "fill_strength": fill,
                "subject_roughness": _clamp(0.48 + step * 0.08, 0.18, 0.84),
            },
        )

    color_targets = (
        (0.42, 0.62, 1.0, 1.0),
        (1.0, 0.36, 0.18, 1.0),
        (1.0, 0.80, 0.46, 1.0),
        (0.58, 1.0, 0.54, 1.0),
        (1.0, 0.28, 0.92, 1.0),
    )
    shapes = (
        (0.42, 1.55, 7.0),
        (0.72, 1.08, -4.0),
        (1.25, 0.72, 0.0),
        (2.25, 0.28, 7.0),
        (2.85, 1.45, -10.0),
    )
    neutral = (1.0, 0.76, 0.46, 1.0)
    for index, step in enumerate(steps):
        width, height, twist = shapes[index % len(shapes)]
        add(
            f"gel_{_step_label(step)}",
            {
                "panel_color": _mix(neutral, color_targets[index % len(color_targets)], 0.88),
                "panel_width": width,
                "panel_height": height,
                "panel_twist": twist,
                "panel_strength": 18.0 + abs(step) * 5.0,
            },
        )

    return variants


def clear_scene() -> None:
    import bpy

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def _cube(name: str, location, scale, mat: Any, rotation=(0.0, 0.0, 0.0)) -> Any:
    import bpy

    bpy.ops.mesh.primitive_cube_add(size=1, location=location, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(mat)
    return obj


def _shade_smooth(obj: Any) -> None:
    import bpy

    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.shade_smooth()
    obj.select_set(False)


def _add_set(settings: MeshLightSettings) -> None:
    import bpy

    floor = principled_material("mesh light floor", (0.21, 0.20, 0.22, 1.0), roughness=0.82)
    wall_color = _mix((0.10, 0.11, 0.16, 1.0), (0.36, 0.24, 0.18, 1.0), settings.room_warmth)
    wall = principled_material("mesh light wall", wall_color, roughness=0.9)
    matte = principled_material("matte hero object", (0.74, 0.66, 0.52, 1.0), roughness=settings.subject_roughness)
    chrome = principled_material("soft chrome ball", (0.78, 0.82, 0.88, 1.0), roughness=0.18, metallic=1.0)
    dark = principled_material("shadow card material", (0.045, 0.04, 0.038, 1.0), roughness=0.78)

    bpy.ops.mesh.primitive_plane_add(size=5.2, location=(0, 0.15, 0))
    floor_obj = bpy.context.object
    floor_obj.name = "mesh light floor"
    floor_obj.data.materials.append(floor)

    bpy.ops.mesh.primitive_plane_add(size=5.2, location=(0, 2.05, 1.55), rotation=(math.pi / 2, 0, 0))
    wall_obj = bpy.context.object
    wall_obj.name = "mesh light wall"
    wall_obj.data.materials.append(wall)

    bpy.ops.mesh.primitive_uv_sphere_add(segments=36, ring_count=18, radius=0.58, location=(0.0, 0.36, 0.62))
    hero = bpy.context.object
    hero.name = "matte light read sphere"
    hero.scale = (0.85, 0.85, 1.08)
    hero.data.materials.append(matte)
    _shade_smooth(hero)

    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=0.28, location=(-0.86, 0.16, 0.32))
    ball = bpy.context.object
    ball.name = "specular light read ball"
    ball.data.materials.append(chrome)
    _shade_smooth(ball)

    _cube("shadow card", (0.72, 0.18, 0.46), (0.08 * settings.shadow_blocker_scale, 0.25, 0.46 * settings.shadow_blocker_scale), dark, rotation=(0, 0, math.radians(-9)))
    _cube("small shadow step", (0.95, -0.22, 0.12), (0.42, 0.18, 0.12), dark)


def _add_mesh_light(settings: MeshLightSettings) -> None:
    mat = emission_material("visible emissive mesh light", settings.panel_color, settings.panel_strength)
    panel = _cube(
        "emissive softbox mesh",
        (settings.panel_x, settings.panel_y, settings.panel_z),
        (settings.panel_width, settings.panel_depth, settings.panel_height),
        mat,
        rotation=(0.0, 0.0, math.radians(settings.panel_twist)),
    )
    look_at(panel, (0.0, 0.42, 0.64))


def _add_fill(settings: MeshLightSettings) -> None:
    import bpy

    if settings.fill_strength <= 0:
        return
    bpy.ops.object.light_add(type="AREA", location=(1.55, -1.9, 1.85))
    fill = bpy.context.object
    fill.name = "weak studio fill"
    fill.data.energy = settings.fill_strength
    fill.data.size = 3.6
    fill.data.color = (0.42, 0.52, 0.78)
    look_at(fill, (0.0, 0.4, 0.64))


def _add_camera() -> None:
    add_orbit_camera(
        name=MESH_LIGHT_CAMERA,
        target=(0.0, 0.42, 0.62),
        distance=4.2,
        lens_mm=56.0,
        yaw_degrees=-2.0,
        pitch_degrees=10.0,
    )


def build_mesh_light_scene(settings: MeshLightSettings | Mapping[str, Any] | None = None) -> None:
    import bpy

    mesh_settings = coerce_mesh_light_settings(settings)
    clear_scene()
    world = bpy.context.scene.world or bpy.data.worlds.new("mesh light world")
    bpy.context.scene.world = world
    world.color = (0.01, 0.011, 0.016)
    _add_set(mesh_settings)
    _add_mesh_light(mesh_settings)
    _add_fill(mesh_settings)
    _add_camera()
