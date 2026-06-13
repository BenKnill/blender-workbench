from __future__ import annotations

import dataclasses
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from blender_workbench.camera import add_orbit_camera, look_at
from blender_workbench.materials import emission_material, principled_material
from blender_workbench.sweep import SweepVariant


@dataclass(frozen=True)
class VirtualSetSettings:
    set_width: float = 4.8
    set_depth: float = 5.6
    subject_height: float = 1.25
    foreground_scale: float = 1.0
    horizon_height: float = 1.35
    backlight_strength: float = 2.4


@dataclass(frozen=True)
class CameraShot:
    name: str
    label: str
    lens_mm: float
    distance: float
    yaw_degrees: float
    pitch_degrees: float
    target: tuple[float, float, float] = (0.0, 0.45, 0.78)
    roll_degrees: float = 0.0
    role: str = "candidate"
    note: str = ""


def coerce_virtual_set_settings(settings: VirtualSetSettings | Mapping[str, Any] | None = None) -> VirtualSetSettings:
    if isinstance(settings, VirtualSetSettings):
        return settings
    data = dataclasses.asdict(VirtualSetSettings())
    if settings:
        data.update({key: value for key, value in dict(settings).items() if key in data})
    return VirtualSetSettings(**data)


def coerce_camera_shot(value: CameraShot | Mapping[str, Any]) -> CameraShot:
    if isinstance(value, CameraShot):
        return value
    data = dict(value)
    if "target" in data:
        data["target"] = tuple(data["target"])
    return CameraShot(**data)


def virtual_set_camera_shots() -> tuple[CameraShot, ...]:
    return (
        CameraShot(
            name="wide_establishing",
            label="wide",
            lens_mm=30.0,
            distance=6.2,
            yaw_degrees=-3.0,
            pitch_degrees=12.0,
            note="full set read with foreground, subject, and horizon",
        ),
        CameraShot(
            name="low_foreground",
            label="low fg",
            lens_mm=40.0,
            distance=4.9,
            yaw_degrees=-18.0,
            pitch_degrees=4.0,
            target=(0.0, 0.25, 0.52),
            note="low camera should keep foreground from swallowing subject",
        ),
        CameraShot(
            name="side_profile",
            label="profile",
            lens_mm=56.0,
            distance=5.0,
            yaw_degrees=68.0,
            pitch_degrees=10.0,
            target=(0.0, 0.45, 0.82),
            note="profile view checks depth cue separation",
        ),
        CameraShot(
            name="high_three_quarter",
            label="high 3q",
            lens_mm=42.0,
            distance=5.7,
            yaw_degrees=-34.0,
            pitch_degrees=27.0,
            target=(0.0, 0.45, 0.72),
            note="high three-quarter should still show set layers",
        ),
        CameraShot(
            name="tele_detail",
            label="tele",
            lens_mm=95.0,
            distance=8.5,
            yaw_degrees=14.0,
            pitch_degrees=11.0,
            target=(0.1, 0.48, 0.86),
            note="compressed detail checks whether lighting and depth survive long lens",
        ),
        CameraShot(
            name="backlight_silhouette_fail",
            label="fail back",
            lens_mm=50.0,
            distance=4.6,
            yaw_degrees=178.0,
            pitch_degrees=7.0,
            target=(0.0, 0.45, 0.78),
            role="failure_anchor",
            note="deliberate back view should expose silhouette and horizon failures",
        ),
    )


def virtual_set_camera_variants(
    *,
    scene_settings: VirtualSetSettings | Mapping[str, Any] | None = None,
    camera_shots: Iterable[CameraShot | Mapping[str, Any]] | None = None,
    prefix: str = "vset",
) -> list[SweepVariant]:
    settings = coerce_virtual_set_settings(scene_settings)
    shots = tuple(coerce_camera_shot(shot) for shot in (camera_shots or virtual_set_camera_shots()))
    scene_payload = dataclasses.asdict(settings)
    variants = []
    for shot in shots:
        data = {
            "scene": scene_payload,
            "camera": dataclasses.asdict(shot),
        }
        variants.append(
            SweepVariant(
                name=f"{prefix}_{shot.name}" if prefix else shot.name,
                label=shot.label,
                settings=data,
                note=shot.note,
                role=shot.role,
                tags=("multi_camera", "virtual_set"),
            )
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


def _add_set(settings: VirtualSetSettings) -> None:
    import bpy

    floor_mat = principled_material("virtual set floor", (0.20, 0.21, 0.23, 1.0), roughness=0.86)
    wall_mat = principled_material("virtual set walls", (0.16, 0.18, 0.24, 1.0), roughness=0.9)
    subject_mat = principled_material("virtual set subject", (0.78, 0.66, 0.45, 1.0), roughness=0.58)
    cool_mat = principled_material("cool foreground anchors", (0.26, 0.47, 0.86, 1.0), roughness=0.62)
    warm_mat = principled_material("warm horizon blocks", (0.92, 0.54, 0.28, 1.0), roughness=0.64)
    dark_mat = principled_material("silhouette failure cards", (0.045, 0.046, 0.052, 1.0), roughness=0.8)
    rim_mat = emission_material("virtual rim light cards", (0.72, 0.86, 1.0, 1.0), settings.backlight_strength)

    bpy.ops.mesh.primitive_plane_add(size=settings.set_width, location=(0, 0.4, 0))
    floor = bpy.context.object
    floor.name = "virtual set floor"
    floor.scale.y = settings.set_depth / settings.set_width
    floor.data.materials.append(floor_mat)

    bpy.ops.mesh.primitive_plane_add(size=settings.set_width, location=(0, settings.set_depth * 0.46, 1.75), rotation=(math.pi / 2, 0, 0))
    wall = bpy.context.object
    wall.name = "virtual set rear wall"
    wall.data.materials.append(wall_mat)

    for index, x in enumerate((-1.7, -0.8, 0.8, 1.7), start=1):
        height = settings.horizon_height * (0.65 + index * 0.11)
        _cube(f"horizon block {index}", (x, settings.set_depth * 0.32, height * 0.5), (0.22, 0.18, height), warm_mat)

    for index, (x, y) in enumerate(((-1.25, -1.05), (1.1, -0.55), (-0.65, 0.1), (1.32, 0.42)), start=1):
        scale = settings.foreground_scale * (0.55 + index * 0.08)
        _cube(f"foreground anchor {index}", (x, y, scale * 0.18), (0.18 * scale, 0.2 * scale, 0.36 * scale), cool_mat)

    bpy.ops.mesh.primitive_uv_sphere_add(segments=36, ring_count=18, radius=0.58, location=(0.0, 0.45, settings.subject_height * 0.48))
    subject = bpy.context.object
    subject.name = "virtual set hero subject"
    subject.scale = (0.82, 0.82, settings.subject_height)
    subject.data.materials.append(subject_mat)

    _cube("silhouette side card", (-0.92, 0.46, 0.62), (0.08, 0.34, 0.62), dark_mat, rotation=(0, 0, math.radians(-8)))
    _cube("rim glow card", (0.0, settings.set_depth * 0.38, 1.18), (1.6, 0.035, 0.28), rim_mat)


def _add_lights(settings: VirtualSetSettings) -> None:
    import bpy

    bpy.ops.object.light_add(type="AREA", location=(-1.7, -1.7, 2.9))
    key = bpy.context.object
    key.name = "virtual set key softbox"
    key.data.energy = 520
    key.data.size = 3.2
    look_at(key, (0.0, 0.45, 0.8))

    bpy.ops.object.light_add(type="POINT", location=(1.4, settings.set_depth * 0.34, 1.45))
    rim = bpy.context.object
    rim.name = "virtual set rim light"
    rim.data.energy = 90 * settings.backlight_strength


def build_virtual_set_camera_scene(settings: Mapping[str, Any] | None = None) -> None:
    import bpy

    payload = dict(settings or {})
    scene_settings = coerce_virtual_set_settings(payload.get("scene", payload))
    shot = coerce_camera_shot(payload.get("camera", dataclasses.asdict(virtual_set_camera_shots()[0])))
    clear_scene()
    world = bpy.context.scene.world or bpy.data.worlds.new("virtual set world")
    bpy.context.scene.world = world
    world.color = (0.012, 0.014, 0.022)
    _add_set(scene_settings)
    _add_lights(scene_settings)
    camera = add_orbit_camera(
        name=f"virtual camera {shot.name}",
        target=shot.target,
        distance=shot.distance,
        lens_mm=shot.lens_mm,
        yaw_degrees=shot.yaw_degrees,
        pitch_degrees=shot.pitch_degrees,
    )
    camera.rotation_euler.rotate_axis("Z", math.radians(shot.roll_degrees))
    bpy.context.scene.camera = camera
