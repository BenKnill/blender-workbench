from __future__ import annotations

import dataclasses
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from blender_workbench.camera import add_orbit_camera
from blender_workbench.materials import principled_material
from blender_workbench.sweep import SweepVariant


TRANSPARENCY_CAMERA = "transparency_camera"


@dataclass(frozen=True)
class TransparencySettings:
    color: tuple[float, float, float, float] = (0.66, 0.82, 1.0, 1.0)
    alpha: float = 0.45
    transmission_weight: float = 0.35
    roughness: float = 0.08
    ior: float = 1.45
    pane_count: int = 3
    pane_gap: float = 0.28
    pane_thickness: float = 0.055
    sphere_scale: tuple[float, float, float] = (1.0, 1.0, 1.0)
    checker_contrast: float = 1.0
    backlight_energy: float = 360.0
    edge_emission_strength: float = 0.0
    camera_yaw: float = -10.0
    camera_pitch: float = 10.0
    camera_lens: float = 48.0
    camera_distance: float = 4.1


def coerce_transparency_settings(settings: TransparencySettings | Mapping[str, Any] | None = None) -> TransparencySettings:
    if isinstance(settings, TransparencySettings):
        return settings
    data = dataclasses.asdict(TransparencySettings())
    if settings:
        data.update({key: value for key, value in dict(settings).items() if key in data})
    return TransparencySettings(**data)


def _step_label(step: int) -> str:
    return "base" if step == 0 else f"{'p' if step > 0 else 'm'}{abs(step)}"


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _mix_color(a: tuple[float, float, float, float], b: tuple[float, float, float, float], amount: float) -> tuple[float, float, float, float]:
    return (
        a[0] * (1.0 - amount) + b[0] * amount,
        a[1] * (1.0 - amount) + b[1] * amount,
        a[2] * (1.0 - amount) + b[2] * amount,
        1.0,
    )


def transparency_variants(
    *,
    prefix: str = "glass",
    steps: tuple[int, ...] = (-2, -1, 0, 1, 2),
    alpha_center: float = 0.48,
    alpha_stride: float = 0.28,
    roughness_center: float = 0.42,
    roughness_stride: float = 0.32,
    ior_center: float = 1.55,
    ior_stride: float = 0.42,
    thickness_center: float = 0.07,
    thickness_stride: float = 0.075,
    tint_stride: float = 0.24,
) -> list[SweepVariant]:
    """Build a stride board for transparency variables.

    Wider strides are usually better here: subtle glass changes collapse in
    thumbnails unless the background, thickness, or IOR moves far enough.
    """
    base = dataclasses.asdict(TransparencySettings())
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
                note="stride scout: alpha, roughness, IOR, thickness, and tint",
            )
        )

    for step in steps:
        alpha = _clamp(alpha_center + step * alpha_stride, 0.03, 0.98)
        add(
            f"alpha_{_step_label(step)}",
            {
                "alpha": alpha,
                "transmission_weight": _clamp(0.78 - abs(step) * 0.18, 0.18, 0.84),
                "roughness": 0.04,
                "checker_contrast": 1.35,
            },
        )

    for step in steps:
        roughness = _clamp(roughness_center + step * roughness_stride, 0.0, 0.98)
        add(
            f"rough_{_step_label(step)}",
            {
                "alpha": 0.62,
                "transmission_weight": 0.36,
                "roughness": roughness,
                "checker_contrast": 1.45,
            },
        )

    for step in steps:
        ior = _clamp(ior_center + step * ior_stride, 1.01, 2.35)
        scale = 1.05 + abs(step) * 0.23
        add(
            f"ior_{_step_label(step)}",
            {
                "color": (0.82, 0.94, 1.0, 1.0),
                "alpha": 1.0,
                "transmission_weight": 1.0,
                "roughness": 0.0,
                "ior": ior,
                "sphere_scale": (scale, scale, 1.0 + abs(step) * 0.18),
                "pane_count": 1 if abs(step) == 2 else 3,
                "checker_contrast": 1.55,
            },
        )

    for step in steps:
        thickness = _clamp(thickness_center + step * thickness_stride, 0.008, 0.32)
        add(
            f"thick_{_step_label(step)}",
            {
                "color": (0.74, 0.92, 1.0, 1.0),
                "alpha": 1.0 if step >= 0 else 0.54,
                "transmission_weight": _clamp(0.7 + step * 0.08, 0.42, 1.0),
                "roughness": _clamp(0.02 + abs(step) * 0.08, 0.0, 0.4),
                "ior": 1.72,
                "pane_thickness": thickness,
                "pane_gap": _clamp(0.26 - step * 0.035, 0.12, 0.44),
                "checker_contrast": 1.5,
            },
        )

    tint_targets = (
        (0.18, 0.52, 1.0, 1.0),
        (0.96, 0.14, 0.12, 1.0),
        (0.12, 0.95, 0.42, 1.0),
        (1.0, 0.55, 0.10, 1.0),
        (0.72, 0.20, 1.0, 1.0),
    )
    neutral = (0.76, 0.90, 1.0, 1.0)
    for index, step in enumerate(steps):
        amount = _clamp(0.52 + (step + 2) * tint_stride, 0.12, 1.0)
        add(
            f"tint_{_step_label(step)}",
            {
                "color": _mix_color(neutral, tint_targets[index % len(tint_targets)], amount),
                "alpha": _clamp(0.36 + (step + 2) * 0.12, 0.24, 0.88),
                "transmission_weight": 0.34,
                "roughness": 0.12,
                "checker_contrast": 1.35,
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


def _glass_material(settings: TransparencySettings) -> Any:
    emission = None
    if settings.edge_emission_strength > 0:
        emission = (
            min(1.0, settings.color[0] * 1.35),
            min(1.0, settings.color[1] * 1.35),
            min(1.0, settings.color[2] * 1.35),
            1.0,
        )
    return principled_material(
        "transparent study material",
        settings.color,
        roughness=settings.roughness,
        ior=settings.ior,
        alpha=settings.alpha,
        transmission_weight=settings.transmission_weight,
        emission=emission,
        emission_strength=settings.edge_emission_strength,
    )


def _add_checker_wall(settings: TransparencySettings) -> None:
    dark = principled_material("checker dark", (0.03, 0.035, 0.045, 1.0), roughness=0.9)
    bright_value = min(1.0, 0.56 * settings.checker_contrast)
    bright = principled_material("checker bright", (bright_value, bright_value * 0.92, bright_value * 0.78, 1.0), roughness=0.86)
    blue = principled_material("checker blue", (0.16, 0.28, min(1.0, 0.65 * settings.checker_contrast), 1.0), roughness=0.86)
    coral = principled_material("checker coral", (min(1.0, 0.72 * settings.checker_contrast), 0.23, 0.18, 1.0), roughness=0.86)
    mats = [dark, bright, blue, coral]
    for ix in range(7):
        for iz in range(5):
            x = -1.8 + ix * 0.6
            z = 0.35 + iz * 0.42
            mat = mats[(ix + iz * 2) % len(mats)]
            _cube(f"background chip {ix:02d}_{iz:02d}", (x, 1.82, z), (0.29, 0.018, 0.20), mat)


def _add_set(settings: TransparencySettings) -> None:
    import bpy

    floor = principled_material("transparency floor", (0.18, 0.18, 0.20, 1.0), roughness=0.72)
    wall = principled_material("transparency wall", (0.08, 0.09, 0.12, 1.0), roughness=0.88)

    bpy.ops.mesh.primitive_plane_add(size=4.8, location=(0, 0.1, 0))
    floor_obj = bpy.context.object
    floor_obj.name = "transparent material floor"
    floor_obj.data.materials.append(floor)

    bpy.ops.mesh.primitive_plane_add(size=4.8, location=(0, 1.9, 1.35), rotation=(math.pi / 2, 0, 0))
    wall_obj = bpy.context.object
    wall_obj.name = "transparent material wall"
    wall_obj.data.materials.append(wall)

    _add_checker_wall(settings)


def _shade_smooth(obj: Any) -> None:
    import bpy

    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.shade_smooth()
    obj.select_set(False)


def _add_glass_objects(settings: TransparencySettings) -> None:
    import bpy

    mat = _glass_material(settings)
    pane_count = max(1, int(settings.pane_count))
    center = (pane_count - 1) * 0.5
    for index in range(pane_count):
        x = (index - center) * settings.pane_gap
        pane = _cube(
            f"transparent pane {index:02d}",
            (x, 0.54 + index * 0.035, 0.92),
            (0.18, settings.pane_thickness, 0.68),
            mat,
            rotation=(0.0, math.radians(index * 7 - center * 7), 0.0),
        )
        bevel = pane.modifiers.new("small polished bevel", "BEVEL")
        bevel.width = 0.035
        bevel.segments = 6
        pane.modifiers.new("weighted normals", "WEIGHTED_NORMAL")

    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=0.38, location=(-0.86, 0.42, 0.55))
    sphere = bpy.context.object
    sphere.name = "transparent round lens"
    sphere.scale = settings.sphere_scale
    sphere.data.materials.append(mat)
    _shade_smooth(sphere)

    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=0.22, location=(0.92, 0.35, 0.36))
    bead = bpy.context.object
    bead.name = "small tint bead"
    bead.scale = (0.82, 0.82, 0.82)
    bead.data.materials.append(mat)
    _shade_smooth(bead)


def _add_lights(settings: TransparencySettings) -> None:
    import bpy

    bpy.ops.object.light_add(type="AREA", location=(-1.6, -1.9, 2.2))
    key = bpy.context.object
    key.name = "large reflection key"
    key.data.energy = 420
    key.data.size = 3.3
    key.data.color = (0.94, 0.86, 1.0)

    bpy.ops.object.light_add(type="AREA", location=(0.0, 1.45, 1.25))
    back = bpy.context.object
    back.name = "checker backlight"
    back.data.energy = settings.backlight_energy
    back.data.size = 1.6
    back.data.color = (1.0, 0.70, 0.44)


def _add_camera(settings: TransparencySettings) -> None:
    add_orbit_camera(
        name=TRANSPARENCY_CAMERA,
        target=(0.0, 0.56, 0.72),
        distance=settings.camera_distance,
        lens_mm=settings.camera_lens,
        yaw_degrees=settings.camera_yaw,
        pitch_degrees=settings.camera_pitch,
    )


def build_transparency_scene(settings: TransparencySettings | Mapping[str, Any] | None = None) -> None:
    import bpy

    transparency_settings = coerce_transparency_settings(settings)
    clear_scene()
    world = bpy.context.scene.world or bpy.data.worlds.new("transparency world")
    bpy.context.scene.world = world
    world.color = (0.018, 0.018, 0.026)
    _add_set(transparency_settings)
    _add_glass_objects(transparency_settings)
    _add_lights(transparency_settings)
    _add_camera(transparency_settings)
