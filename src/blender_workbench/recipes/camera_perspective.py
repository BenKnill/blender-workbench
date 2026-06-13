from __future__ import annotations

import dataclasses
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from blender_workbench.camera import add_orbit_camera, camera_distance_for_matching_framing
from blender_workbench.materials import principled_material
from blender_workbench.sweep import SweepVariant


CAMERA_PERSPECTIVE_CAMERA = "perspective_scout_camera"


@dataclass(frozen=True)
class CameraPerspectiveSettings:
    camera_lens: float = 45.0
    camera_distance: float = camera_distance_for_matching_framing(45.0)
    camera_yaw: float = 0.0
    camera_pitch: float = 10.0
    camera_roll: float = 0.0
    subject_scale: tuple[float, float, float] = (0.72, 0.72, 1.0)
    foreground_marker_scale: float = 1.0
    background_marker_scale: float = 1.0
    room_depth: float = 4.6
    light_angle: float = -35.0


def coerce_camera_perspective_settings(
    settings: CameraPerspectiveSettings | Mapping[str, Any] | None = None,
) -> CameraPerspectiveSettings:
    if isinstance(settings, CameraPerspectiveSettings):
        return settings
    data = dataclasses.asdict(CameraPerspectiveSettings())
    if settings:
        data.update({key: value for key, value in dict(settings).items() if key in data})
    return CameraPerspectiveSettings(**data)


def _matched(lens: float) -> float:
    return camera_distance_for_matching_framing(lens, base_lens_mm=58.0, base_distance=4.6)


def _step_label(step: int) -> str:
    return "base" if step == 0 else f"{'p' if step > 0 else 'm'}{abs(step)}"


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def camera_perspective_variants(
    *,
    prefix: str = "cam",
    steps: tuple[int, ...] = (-2, -1, 0, 1, 2),
    lens_center: float = 58.0,
    lens_stride: float = 36.0,
    yaw_stride: float = 34.0,
    pitch_center: float = 18.0,
    pitch_stride: float = 13.0,
    roll_stride: float = 13.0,
    depth_stride: float = 1.05,
) -> list[SweepVariant]:
    """Build a stride board for camera variables.

    Increase the stride values when the perspective sheet looks timid. The
    distance is recalculated for every lens tile so the central subject stays
    roughly comparable while the room perspective changes.
    """
    base = dataclasses.asdict(CameraPerspectiveSettings(camera_lens=lens_center, camera_distance=_matched(lens_center)))
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
                note="stride scout: lens, distance, orbit, roll, and depth",
            )
        )

    for step in steps:
        lens = _clamp(lens_center + step * lens_stride, 14.0, 150.0)
        add(f"lens_{_step_label(step)}", {"camera_lens": lens, "camera_distance": _matched(lens)})

    for step in steps:
        add(f"yaw_{_step_label(step)}", {"camera_yaw": step * yaw_stride})

    for step in steps:
        pitch = _clamp(pitch_center + step * pitch_stride, -6.0, 52.0)
        add(f"pitch_{_step_label(step)}", {"camera_pitch": pitch})

    for step in steps:
        add(f"roll_{_step_label(step)}", {"camera_roll": step * roll_stride})

    for step in steps:
        depth = _clamp(4.6 + step * depth_stride, 2.4, 8.0)
        foreground = _clamp(1.0 - step * 0.28, 0.42, 1.75)
        background = _clamp(1.0 + step * 0.18, 0.55, 1.55)
        add(
            f"depth_{_step_label(step)}",
            {
                "room_depth": depth,
                "foreground_marker_scale": foreground,
                "background_marker_scale": background,
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


def _add_set(settings: CameraPerspectiveSettings) -> None:
    import bpy

    floor = principled_material("perspective floor", (0.29, 0.30, 0.33, 1.0), roughness=0.86)
    wall = principled_material("perspective wall", (0.18, 0.20, 0.27, 1.0), roughness=0.9)
    dark = principled_material("dark lane stripe", (0.06, 0.065, 0.08, 1.0), roughness=0.9)
    warm = principled_material("warm distance blocks", (0.86, 0.54, 0.32, 1.0), roughness=0.68)
    cool = principled_material("cool foreground blocks", (0.32, 0.56, 0.92, 1.0), roughness=0.66)
    subject_mat = principled_material("central camera subject", (0.86, 0.74, 0.52, 1.0), roughness=0.56)

    bpy.ops.mesh.primitive_plane_add(size=6.4, location=(0, 0.35, 0))
    floor_obj = bpy.context.object
    floor_obj.name = "perspective floor"
    floor_obj.data.materials.append(floor)

    bpy.ops.mesh.primitive_plane_add(size=6.4, location=(0, 2.75, 1.8), rotation=(math.pi / 2, 0, 0))
    wall_obj = bpy.context.object
    wall_obj.name = "back wall"
    wall_obj.data.materials.append(wall)

    for x in [-1.2, -0.6, 0.0, 0.6, 1.2]:
        _cube(f"floor depth stripe {x}", (x, 0.25, 0.012), (0.018, settings.room_depth, 0.012), dark)
    for index, y in enumerate([-1.2, -0.4, 0.4, 1.2, 2.0]):
        width = 2.9 - index * 0.22
        _cube(f"floor cross stripe {index:02d}", (0, y, 0.018), (width, 0.015, 0.012), dark)

    for index, y in enumerate([-0.95, -0.25, 0.65, 1.55]):
        marker_scale = settings.foreground_marker_scale if y < 0 else settings.background_marker_scale
        height = (0.38 + index * 0.18) * marker_scale
        x = -1.18 if index % 2 == 0 else 1.18
        mat = cool if y < 0 else warm
        _cube(f"depth marker left {index:02d}", (x, y, height * 0.5), (0.16, 0.16, height), mat)
        _cube(f"depth marker right {index:02d}", (-x, y + 0.16, height * 0.5), (0.16, 0.16, height), mat)

    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=0.72, location=(0.0, 0.28, 0.78))
    subject = bpy.context.object
    subject.name = "matched framing subject"
    subject.scale = settings.subject_scale
    subject.data.materials.append(subject_mat)

    _cube("subject vertical ruler", (0.66, 0.22, 0.72), (0.035, 0.035, 0.72), dark)
    _cube("subject ground ruler", (0.0, -0.18, 0.035), (0.72, 0.035, 0.035), dark)


def _add_lights(settings: CameraPerspectiveSettings) -> None:
    import bpy

    angle = math.radians(settings.light_angle)
    bpy.ops.object.light_add(type="AREA", location=(2.2 * math.cos(angle), -2.0, 3.0 + 0.7 * math.sin(angle)))
    key = bpy.context.object
    key.name = "perspective large key"
    key.data.energy = 520
    key.data.size = 4.2

    bpy.ops.object.light_add(type="POINT", location=(-1.5, 1.6, 1.8))
    rim = bpy.context.object
    rim.name = "small depth rim"
    rim.data.energy = 75
    rim.data.color = (0.55, 0.68, 1.0)


def _add_camera(settings: CameraPerspectiveSettings) -> None:
    add_orbit_camera(
        name=CAMERA_PERSPECTIVE_CAMERA,
        target=(0.0, 0.28, 0.78),
        distance=settings.camera_distance,
        lens_mm=settings.camera_lens,
        yaw_degrees=settings.camera_yaw,
        pitch_degrees=settings.camera_pitch,
        roll_degrees=settings.camera_roll,
    )


def build_camera_perspective_scene(settings: CameraPerspectiveSettings | Mapping[str, Any] | None = None) -> None:
    import bpy

    camera_settings = coerce_camera_perspective_settings(settings)
    clear_scene()
    world = bpy.context.scene.world or bpy.data.worlds.new("camera perspective world")
    bpy.context.scene.world = world
    world.color = (0.025, 0.026, 0.032)
    _add_set(camera_settings)
    _add_lights(camera_settings)
    _add_camera(camera_settings)
