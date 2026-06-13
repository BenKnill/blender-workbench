from __future__ import annotations

import dataclasses
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from blender_workbench.camera import add_orbit_camera, look_at
from blender_workbench.materials import emission_material, principled_material
from blender_workbench.primitives import add_soft_horizon_band
from blender_workbench.sweep import SweepVariant, named_variants


SOFT_ATMOSPHERE_CAMERA = "soft_atmosphere_camera"


@dataclass(frozen=True)
class SoftAtmosphereSettings:
    alpha: float = 0.48
    strength: float = 0.72
    feather_steps: int = 5
    center_fraction: float = 0.34
    noise_strength: float = 0.0
    noise_scale: float = 7.0
    band_height: float = 1.05
    warmth: float = 0.52


def coerce_soft_atmosphere_settings(settings: SoftAtmosphereSettings | Mapping[str, Any] | None = None) -> SoftAtmosphereSettings:
    if isinstance(settings, SoftAtmosphereSettings):
        return settings
    data = dataclasses.asdict(SoftAtmosphereSettings())
    if settings:
        data.update({key: value for key, value in dict(settings).items() if key in data})
    return SoftAtmosphereSettings(**data)


def soft_atmosphere_variants(*, prefix: str = "soft_card") -> list[SweepVariant]:
    return named_variants(
        {
            "hard_edge_fail": {"feather_steps": 0, "center_fraction": 0.92, "alpha": 0.62, "strength": 0.78},
            "narrow_falloff": {"feather_steps": 2, "center_fraction": 0.16, "alpha": 0.52},
            "base_soft": {},
            "wide_falloff": {"feather_steps": 7, "center_fraction": 0.62, "band_height": 1.24},
            "low_alpha": {"alpha": 0.24, "strength": 0.86},
            "high_alpha": {"alpha": 0.72, "strength": 0.64},
            "low_glow": {"strength": 0.30, "alpha": 0.54},
            "hot_glow": {"strength": 1.24, "alpha": 0.40},
            "fine_noise": {"noise_strength": 0.16, "noise_scale": 18.0},
            "broad_noise": {"noise_strength": 0.22, "noise_scale": 3.2},
            "cool_sheet": {"warmth": 0.08, "strength": 0.82},
            "warm_sheet": {"warmth": 0.92, "strength": 0.78},
        },
        base=dataclasses.asdict(SoftAtmosphereSettings()),
        prefix=prefix,
        note="soft atmosphere card scout: edge hardness, falloff, alpha, glow, noise",
    )


def _mix(a: tuple[float, float, float, float], b: tuple[float, float, float, float], amount: float) -> tuple[float, float, float, float]:
    return (
        a[0] * (1.0 - amount) + b[0] * amount,
        a[1] * (1.0 - amount) + b[1] * amount,
        a[2] * (1.0 - amount) + b[2] * amount,
        1.0,
    )


def clear_scene() -> None:
    import bpy

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def _cube(name: str, location, scale, mat, rotation=(0.0, 0.0, 0.0)) -> Any:
    import bpy

    bpy.ops.mesh.primitive_cube_add(size=1, location=location, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(mat)
    return obj


def _add_stage(settings: SoftAtmosphereSettings) -> None:
    import bpy

    floor_mat = principled_material("matte charcoal floor", (0.055, 0.052, 0.058, 1.0), roughness=0.9)
    wall_mat = principled_material("deep blue diagnostic wall", (0.035, 0.045, 0.07, 1.0), roughness=0.88)
    post_mat = principled_material("dark foreground posts", (0.025, 0.023, 0.025, 1.0), roughness=0.82)
    marker_mat = emission_material("small diagnostic glints", (0.75, 0.86, 1.0, 1.0), 0.18)

    bpy.ops.mesh.primitive_plane_add(size=7.0, location=(0.0, 0.0, -0.02))
    floor = bpy.context.object
    floor.name = "matte floor catching card spill"
    floor.data.materials.append(floor_mat)

    bpy.ops.mesh.primitive_plane_add(size=6.0, location=(0.0, 2.8, 1.42), rotation=(math.pi / 2, 0.0, 0.0))
    wall = bpy.context.object
    wall.name = "dark wall exposing card edge"
    wall.scale.z = 0.62
    wall.data.materials.append(wall_mat)

    for index, x in enumerate((-2.1, -1.05, 0.0, 1.05, 2.1)):
        _cube(f"vertical edge marker {index}", (x, 2.64, 0.72), (0.035, 0.035, 0.72), post_mat)
        _cube(f"small horizon tick {index}", (x, 2.60, 0.33), (0.08, 0.025, 0.018), marker_mat)

    color = _mix((0.36, 0.52, 1.0, 1.0), (1.0, 0.54, 0.22, 1.0), settings.warmth)
    add_soft_horizon_band(
        name="diagnostic soft atmosphere card",
        location=(0.0, 2.55, 0.92),
        width=5.5,
        height=settings.band_height,
        color=color,
        strength=settings.strength,
        alpha=settings.alpha,
        feather_steps=settings.feather_steps,
        center_fraction=settings.center_fraction,
        noise_strength=settings.noise_strength,
        noise_scale=settings.noise_scale,
    )


def _add_lights(settings: SoftAtmosphereSettings) -> None:
    import bpy

    color = _mix((0.42, 0.50, 1.0, 1.0), (1.0, 0.62, 0.30, 1.0), settings.warmth)
    bpy.ops.object.light_add(type="AREA", location=(-2.8, -2.4, 2.2))
    key = bpy.context.object
    key.name = "low glancing key"
    key.data.energy = 160
    key.data.size = 3.8
    key.data.color = color[:3]
    look_at(key, (0.0, 1.6, 0.6))


def _configure_world() -> None:
    import bpy

    world = bpy.context.scene.world or bpy.data.worlds.new("soft atmosphere world")
    bpy.context.scene.world = world
    world.color = (0.005, 0.006, 0.010)


def _add_camera() -> None:
    add_orbit_camera(
        name=SOFT_ATMOSPHERE_CAMERA,
        target=(0.0, 1.7, 0.76),
        distance=5.2,
        lens_mm=58.0,
        yaw_degrees=0.0,
        pitch_degrees=4.0,
    )


def build_soft_atmosphere_scene(settings: SoftAtmosphereSettings | Mapping[str, Any] | None = None) -> None:
    soft_settings = coerce_soft_atmosphere_settings(settings)
    clear_scene()
    _configure_world()
    _add_stage(soft_settings)
    _add_lights(soft_settings)
    _add_camera()
