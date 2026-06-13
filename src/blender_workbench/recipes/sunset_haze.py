from __future__ import annotations

import dataclasses
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from blender_workbench.camera import add_orbit_camera, look_at
from blender_workbench.materials import emission_material, principled_material
from blender_workbench.presets import SUNSET_HAZE
from blender_workbench.primitives import add_soft_horizon_band
from blender_workbench.sweep import SweepVariant


SUNSET_HAZE_CAMERA = "sunset_haze_camera"


@dataclass(frozen=True)
class SunsetHazeSettings:
    sky_color: tuple[float, float, float] = (0.22, 0.18, 0.34)
    horizon_color: tuple[float, float, float] = (0.92, 0.34, 0.18)
    haze_density: float = 0.018
    disk_height: float = 0.82
    disk_size: float = 0.18
    disk_strength: float = 1.4
    foreground_contrast: float = 0.82
    horizon_band_height: float = 0.58


def coerce_sunset_haze_settings(settings: SunsetHazeSettings | Mapping[str, Any] | None = None) -> SunsetHazeSettings:
    if isinstance(settings, SunsetHazeSettings):
        return settings
    data = dataclasses.asdict(SunsetHazeSettings())
    if settings:
        data.update({key: value for key, value in dict(settings).items() if key in data})
    return SunsetHazeSettings(**data)


def _with_alpha(color: tuple[float, float, float], alpha: float = 1.0) -> tuple[float, float, float, float]:
    return (color[0], color[1], color[2], alpha)


def sunset_haze_variants(*, prefix: str = "sunset") -> list[SweepVariant]:
    cases: list[tuple[str, Mapping[str, Any]]] = [
        (
            "flat_fail",
            {
                "sky_color": (0.24, 0.22, 0.30),
                "horizon_color": (0.26, 0.24, 0.30),
                "haze_density": 0.004,
                "disk_strength": 0.4,
                "foreground_contrast": 0.24,
            },
        ),
        *SUNSET_HAZE.values,
        (
            "orange_fail",
            {
                "sky_color": (0.85, 0.25, 0.05),
                "horizon_color": (1.0, 0.42, 0.02),
                "haze_density": 0.038,
                "disk_height": 1.05,
                "disk_strength": 2.2,
            },
        ),
        (
            "washout_fail",
            {
                "sky_color": (0.58, 0.52, 0.62),
                "horizon_color": (0.98, 0.78, 0.62),
                "haze_density": 0.078,
                "disk_size": 0.32,
                "disk_strength": 3.0,
                "foreground_contrast": 0.34,
                "horizon_band_height": 0.92,
            },
        ),
    ]
    base = dataclasses.asdict(SunsetHazeSettings())
    variants: list[SweepVariant] = []
    for label, settings in cases:
        data = dict(base)
        data.update(settings)
        variants.append(
            SweepVariant(
                name=f"{prefix}_{label}" if prefix else label,
                label=label,
                settings=data,
                note=SUNSET_HAZE.note,
            )
        )
    return variants


def clear_scene() -> None:
    import bpy

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def _mix(a: tuple[float, float, float], b: tuple[float, float, float], amount: float) -> tuple[float, float, float]:
    return (
        a[0] * (1.0 - amount) + b[0] * amount,
        a[1] * (1.0 - amount) + b[1] * amount,
        a[2] * (1.0 - amount) + b[2] * amount,
    )


def _cube(name: str, location, scale, mat, rotation=(0.0, 0.0, 0.0)) -> Any:
    import bpy

    bpy.ops.mesh.primitive_cube_add(size=1, location=location, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(mat)
    return obj


def _add_sky(settings: SunsetHazeSettings) -> None:
    import bpy

    sky = principled_material("ordered sky color", _with_alpha(settings.sky_color), roughness=1.0)
    horizon = _mix(settings.horizon_color, settings.sky_color, 0.25)
    band_alpha = max(0.04, min(0.72, settings.haze_density * 11.0))
    band_strength = 0.18 + min(1.4, settings.haze_density * 18.0)

    bpy.ops.mesh.primitive_plane_add(size=7.5, location=(0.0, 3.1, 1.28), rotation=(math.pi / 2, 0.0, 0.0))
    sky_obj = bpy.context.object
    sky_obj.name = "single color sky plane"
    sky_obj.scale.z = 0.68
    sky_obj.data.materials.append(sky)

    add_soft_horizon_band(
        name="sunset haze horizon band",
        location=(0.0, 3.02, 0.58),
        width=7.2,
        height=settings.horizon_band_height,
        color=_with_alpha(horizon),
        strength=band_strength,
        alpha=band_alpha,
        feather_steps=5,
        center_fraction=0.42,
        noise_strength=min(0.18, settings.haze_density * 2.2),
        noise_scale=4.2,
    )

    disk_color = _mix((0.86, 0.90, 1.0), settings.horizon_color, 0.58)
    disk = emission_material("distant disk", _with_alpha(disk_color), settings.disk_strength)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=settings.disk_size, location=(0.92, 2.86, settings.disk_height))
    obj = bpy.context.object
    obj.name = "distant sun moon disk"
    obj.scale.y = 0.08
    obj.data.materials.append(disk)


def _add_foreground(settings: SunsetHazeSettings) -> None:
    dark = max(0.02, 0.20 * (1.0 - settings.foreground_contrast))
    fg = principled_material("foreground silhouette value", (dark, dark * 1.05, dark * 1.18, 1.0), roughness=0.96)
    _cube("flat horizon land mass", (0.0, 1.95, 0.13), (3.9, 0.22, 0.18), fg)
    for index, x in enumerate((-2.2, -1.35, -0.42, 0.64, 1.72)):
        height = 0.28 + 0.16 * ((index % 3) / 2)
        _cube(f"foreground scale marker {index}", (x, 1.38 + index * 0.03, 0.20 + height * 0.5), (0.13, 0.12, height), fg, rotation=(0, 0, index * 0.09))


def _add_lights(settings: SunsetHazeSettings) -> None:
    import bpy

    color = _mix((0.35, 0.44, 0.75), settings.horizon_color, 0.44)
    bpy.ops.object.light_add(type="AREA", location=(-2.4, -1.8, 2.0))
    key = bpy.context.object
    key.name = "low dusk fill"
    key.data.energy = 80 + settings.disk_strength * 30
    key.data.size = 5.5
    key.data.color = color
    look_at(key, (0.0, 1.6, 0.45))


def _configure_world(settings: SunsetHazeSettings) -> None:
    import bpy

    world = bpy.context.scene.world or bpy.data.worlds.new("sunset haze world")
    bpy.context.scene.world = world
    world.color = _mix(settings.sky_color, (0.0, 0.0, 0.0), 0.52)


def _add_camera() -> None:
    add_orbit_camera(
        name=SUNSET_HAZE_CAMERA,
        target=(0.0, 2.0, 0.72),
        distance=4.8,
        lens_mm=58.0,
        yaw_degrees=0.0,
        pitch_degrees=3.0,
    )


def build_sunset_haze_scene(settings: SunsetHazeSettings | Mapping[str, Any] | None = None) -> None:
    haze_settings = coerce_sunset_haze_settings(settings)
    clear_scene()
    _configure_world(haze_settings)
    _add_sky(haze_settings)
    _add_foreground(haze_settings)
    _add_lights(haze_settings)
    _add_camera()
