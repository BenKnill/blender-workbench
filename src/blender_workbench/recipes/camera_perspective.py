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
    camera_lens: float = 58.0
    camera_distance: float = camera_distance_for_matching_framing(58.0, base_lens_mm=58.0, base_distance=4.6)
    camera_yaw: float = 0.0
    camera_pitch: float = 12.0
    camera_roll: float = 0.0
    subject_scale: tuple[float, float, float] = (0.72, 0.72, 1.0)
    subject_y: float = 0.28
    subject_depth: float = 1.0
    foreground_depth: float = 1.0
    foreground_marker_scale: float = 1.0
    background_depth: float = 1.0
    background_marker_scale: float = 1.0
    floor_grid_depth: float = 1.0
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
    foreground_stride: float = 0.45,
    background_stride: float = 0.45,
    grid_stride: float = 0.46,
    subject_stride: float = 0.36,
) -> list[SweepVariant]:
    """Build a same-view stride board for perspective/depth variables.

    Increase the stride values when the sheet looks timid. The lens row uses
    matched distance, while other rows keep the same camera view and alter the
    scene's depth cues.
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
                note="same-view stride scout: lens, foreground, background, grid, subject",
            )
        )

    for step in steps:
        lens = _clamp(lens_center + step * lens_stride, 14.0, 150.0)
        add(f"lens_{_step_label(step)}", {"camera_lens": lens, "camera_distance": _matched(lens)})

    for step in steps:
        depth = _clamp(1.0 + step * foreground_stride, 0.18, 2.2)
        add(
            f"fg_{_step_label(step)}",
            {
                "foreground_depth": depth,
                "foreground_marker_scale": _clamp(0.55 + depth * 0.54, 0.45, 1.85),
            },
        )

    for step in steps:
        depth = _clamp(1.0 + step * background_stride, 0.22, 2.35)
        add(
            f"bg_{_step_label(step)}",
            {
                "background_depth": depth,
                "background_marker_scale": _clamp(1.35 - (depth - 1.0) * 0.32, 0.50, 1.62),
                "room_depth": _clamp(4.6 + (depth - 1.0) * 1.55, 2.7, 7.0),
            },
        )

    for step in steps:
        grid = _clamp(1.0 + step * grid_stride, 0.25, 2.4)
        add(
            f"grid_{_step_label(step)}",
            {
                "floor_grid_depth": grid,
                "room_depth": _clamp(4.6 * grid, 2.4, 8.0),
            },
        )

    for step in steps:
        subject = _clamp(1.0 + step * subject_stride, 0.30, 1.95)
        add(
            f"subj_{_step_label(step)}",
            {
                "subject_y": _clamp(0.28 + step * 0.24, -0.22, 0.92),
                "subject_depth": subject,
                "subject_scale": (0.72, 0.72 * subject, 1.0),
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

    wall_y = 2.05 + settings.background_depth * 0.72
    bpy.ops.mesh.primitive_plane_add(size=6.4, location=(0, wall_y, 1.8), rotation=(math.pi / 2, 0, 0))
    wall_obj = bpy.context.object
    wall_obj.name = "back wall"
    wall_obj.data.materials.append(wall)

    x_count = max(3, min(9, round(3 + settings.floor_grid_depth * 3)))
    x_positions = [-1.45 + index * (2.9 / max(1, x_count - 1)) for index in range(x_count)]
    for index, x in enumerate(x_positions):
        _cube(f"floor depth stripe {index:02d}", (x, 0.25, 0.012), (0.018, settings.room_depth * settings.floor_grid_depth, 0.012), dark)
    cross_count = max(3, min(11, round(3 + settings.floor_grid_depth * 4)))
    for index in range(cross_count):
        t = index / max(1, cross_count - 1)
        scaled_y = (-1.25 + t * 3.25) * settings.floor_grid_depth
        width = 3.0 - t * 1.35
        _cube(f"floor cross stripe {index:02d}", (0, scaled_y, 0.018), (width, 0.015, 0.012), dark)

    for index, y in enumerate([-0.95, -0.25, 0.65, 1.55]):
        is_foreground = y < 0
        marker_scale = settings.foreground_marker_scale if is_foreground else settings.background_marker_scale
        depth_scale = settings.foreground_depth if is_foreground else settings.background_depth
        marker_y = y * depth_scale - (max(0.0, depth_scale - 1.0) * 0.25 if is_foreground else 0.0)
        height = (0.38 + index * 0.18) * marker_scale
        x_abs = 1.18
        if is_foreground:
            x_abs = _clamp(1.24 - max(0.0, depth_scale - 1.0) * 0.32, 0.78, 1.35)
        else:
            x_abs = _clamp(1.02 + max(0.0, depth_scale - 1.0) * 0.22, 0.86, 1.38)
        x = -x_abs if index % 2 == 0 else x_abs
        mat = cool if y < 0 else warm
        marker_width = 0.16 * (1.0 + max(0.0, depth_scale - 1.0) * (0.55 if is_foreground else 0.18))
        _cube(f"depth marker left {index:02d}", (x, marker_y, height * 0.5), (marker_width, 0.16, height), mat)
        _cube(f"depth marker right {index:02d}", (-x, marker_y + 0.16 * depth_scale, height * 0.5), (marker_width, 0.16, height), mat)

    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=0.72, location=(0.0, settings.subject_y, 0.78))
    subject = bpy.context.object
    subject.name = "matched framing subject"
    subject.scale = settings.subject_scale
    subject.data.materials.append(subject_mat)

    _cube("subject vertical ruler", (0.66, settings.subject_y - 0.06, 0.72), (0.035, 0.035, 0.72), dark)
    _cube("subject ground ruler", (0.0, settings.subject_y - 0.46, 0.035), (0.72, 0.035, 0.035), dark)


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
