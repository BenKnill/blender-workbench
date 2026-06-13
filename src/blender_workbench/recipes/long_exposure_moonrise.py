from __future__ import annotations

import dataclasses
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from blender_workbench.camera import add_orbit_camera, look_at
from blender_workbench.materials import emission_material, principled_material, transparent_emission_material
from blender_workbench.primitives import add_soft_horizon_band
from blender_workbench.sweep import SweepVariant


LONG_EXPOSURE_MOONRISE_CAMERA = "long_exposure_moonrise_camera"


@dataclass(frozen=True)
class LongExposureMoonriseSettings:
    streak_length: float = 1.42
    streak_angle: float = 9.0
    trail_thickness: float = 0.022
    terminal_softness: float = 0.12
    halo_radius: float = 0.18
    halo_strength: float = 0.42
    core_strength: float = 1.15
    sky_exposure: float = 0.34
    horizon_haze: float = 0.34
    moon_warmth: float = 0.38
    foreground_contrast: float = 0.78
    horizon_height: float = 0.34


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _clamp01(value: float) -> float:
    return _clamp(value, 0.0, 1.0)


def _mix(
    a: tuple[float, float, float, float],
    b: tuple[float, float, float, float],
    amount: float,
) -> tuple[float, float, float, float]:
    t = _clamp01(amount)
    return (
        a[0] * (1.0 - t) + b[0] * t,
        a[1] * (1.0 - t) + b[1] * t,
        a[2] * (1.0 - t) + b[2] * t,
        1.0,
    )


def coerce_long_exposure_moonrise_settings(
    settings: LongExposureMoonriseSettings | Mapping[str, Any] | None = None,
) -> LongExposureMoonriseSettings:
    if isinstance(settings, LongExposureMoonriseSettings):
        return settings
    data = dataclasses.asdict(LongExposureMoonriseSettings())
    if settings:
        data.update({key: value for key, value in dict(settings).items() if key in data})
    return LongExposureMoonriseSettings(**data)


def moonrise_trail_descriptor(settings: LongExposureMoonriseSettings | Mapping[str, Any] | None = None) -> dict[str, Any]:
    moonrise = coerce_long_exposure_moonrise_settings(settings)
    return {
        "technique": "cheap_emissive_geometry",
        "physical_motion_blur": False,
        "streak_length": max(0.05, float(moonrise.streak_length)),
        "streak_angle": float(moonrise.streak_angle),
        "trail_thickness": max(0.002, float(moonrise.trail_thickness)),
        "terminal_softness": _clamp01(moonrise.terminal_softness),
        "halo_radius": max(0.0, float(moonrise.halo_radius)),
        "halo_strength": max(0.0, float(moonrise.halo_strength)),
        "sky_exposure": _clamp(moonrise.sky_exposure, 0.0, 1.2),
        "horizon_haze": _clamp01(moonrise.horizon_haze),
        "moon_warmth": _clamp01(moonrise.moon_warmth),
        "diagnostics": ("horizon_land_mass", "foreground_scale_markers", "haze_band", "trail_terminals"),
    }


def _variant_settings(overrides: Mapping[str, Any]) -> dict[str, Any]:
    data = dataclasses.asdict(LongExposureMoonriseSettings())
    data.update(dict(overrides))
    moonrise = coerce_long_exposure_moonrise_settings(data)
    payload = dataclasses.asdict(moonrise)
    payload["moonrise_trail"] = moonrise_trail_descriptor(moonrise)
    return payload


def long_exposure_moonrise_variants(*, prefix: str = "moontrail") -> list[SweepVariant]:
    cases: tuple[tuple[str, Mapping[str, Any]], ...] = (
        ("cool_short", {"streak_length": 0.92, "moon_warmth": 0.16, "halo_radius": 0.12, "sky_exposure": 0.28}),
        ("balanced_rise", {}),
        ("long_warm", {"streak_length": 1.88, "moon_warmth": 0.72, "halo_radius": 0.22, "streak_angle": 7.0}),
        ("steep_climb", {"streak_angle": 18.0, "streak_length": 1.36, "terminal_softness": 0.16}),
        ("soft_terminal", {"terminal_softness": 0.28, "halo_radius": 0.24, "halo_strength": 0.50}),
        ("broad_halo", {"halo_radius": 0.36, "halo_strength": 0.72, "core_strength": 1.0}),
        ("hazy_horizon", {"horizon_haze": 0.68, "sky_exposure": 0.42, "foreground_contrast": 0.62}),
        ("crisp_foreground", {"foreground_contrast": 0.96, "horizon_haze": 0.22, "sky_exposure": 0.30}),
        ("torch_fail", {"moon_warmth": 0.96, "core_strength": 3.2, "halo_strength": 1.1, "sky_exposure": 0.54}),
        ("flat_bar_fail", {"terminal_softness": 0.01, "halo_radius": 0.02, "halo_strength": 0.08, "trail_thickness": 0.034}),
        ("washout_fail", {"halo_radius": 0.76, "halo_strength": 1.8, "sky_exposure": 0.92, "horizon_haze": 0.92, "foreground_contrast": 0.22}),
    )
    roles = {
        "balanced_rise": "baseline",
        "torch_fail": "failure_anchor",
        "flat_bar_fail": "failure_anchor",
        "washout_fail": "failure_anchor",
    }
    tags_by_label = {
        "torch_fail": ("too_saturated", "torch"),
        "flat_bar_fail": ("flat_bar",),
        "washout_fail": ("overbloom", "washout"),
    }
    variants: list[SweepVariant] = []
    for label, overrides in cases:
        name = f"{prefix}_{label}" if prefix else label
        variants.append(
            SweepVariant(
                name=name,
                label=label,
                settings=_variant_settings(overrides),
                note="long-exposure moonrise trail scout using cheap emissive geometry",
                role=roles.get(label, "candidate"),
                tags=("long_exposure_moonrise", "moon_trail", *tags_by_label.get(label, ())),
            )
        )
    return variants


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


def _curve(name: str, points: list[tuple[float, float, float]], radius: float, mat: Any, *, resolution: int = 3) -> Any:
    import bpy

    curve = bpy.data.curves.new(name, type="CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = resolution
    curve.bevel_depth = max(0.001, radius)
    curve.bevel_resolution = 5
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for point, co in zip(spline.points, points, strict=True):
        point.co = (co[0], co[1], co[2], 1.0)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    return obj


def _trail_points(settings: LongExposureMoonriseSettings) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    length = max(0.05, settings.streak_length)
    angle = math.radians(settings.streak_angle)
    center = (0.34, 2.86, 1.28)
    dx = math.cos(angle) * length * 0.5
    dz = math.sin(angle) * length * 0.5
    return (center[0] - dx, center[1], center[2] - dz), (center[0] + dx, center[1], center[2] + dz)


def _sky_color(settings: LongExposureMoonriseSettings) -> tuple[float, float, float, float]:
    base = _mix((0.045, 0.060, 0.110, 1.0), (0.22, 0.18, 0.32, 1.0), settings.sky_exposure)
    return _mix(base, (0.42, 0.30, 0.22, 1.0), settings.moon_warmth * 0.18)


def _moon_color(settings: LongExposureMoonriseSettings) -> tuple[float, float, float, float]:
    return _mix((0.72, 0.82, 1.0, 1.0), (1.0, 0.68, 0.34, 1.0), settings.moon_warmth)


def _configure_world(settings: LongExposureMoonriseSettings) -> None:
    import bpy

    world = bpy.context.scene.world or bpy.data.worlds.new("long exposure moonrise world")
    bpy.context.scene.world = world
    sky = _sky_color(settings)
    world.color = (sky[0] * 0.16, sky[1] * 0.16, sky[2] * 0.18)


def _add_sky(settings: LongExposureMoonriseSettings) -> None:
    import bpy

    sky = principled_material("long exposure sky plane", _sky_color(settings), roughness=1.0)
    bpy.ops.mesh.primitive_plane_add(size=7.4, location=(0.0, 3.10, 1.36), rotation=(math.pi / 2, 0.0, 0.0))
    sky_obj = bpy.context.object
    sky_obj.name = "long exposure sky plane"
    sky_obj.scale.z = 0.70
    sky_obj.data.materials.append(sky)

    haze_color = _mix((0.20, 0.22, 0.36, 1.0), (0.88, 0.52, 0.28, 1.0), settings.moon_warmth)
    add_soft_horizon_band(
        name="moonrise horizon haze band",
        location=(0.0, 3.02, 0.58),
        width=7.2,
        height=0.42 + settings.horizon_haze * 0.54,
        color=haze_color,
        strength=0.16 + settings.horizon_haze * 0.68,
        alpha=0.06 + settings.horizon_haze * 0.46,
        feather_steps=6,
        center_fraction=0.36,
        noise_strength=min(0.22, settings.horizon_haze * 0.24),
        noise_scale=4.0,
    )


def _add_foreground(settings: LongExposureMoonriseSettings) -> None:
    contrast = _clamp01(settings.foreground_contrast)
    dark = max(0.01, 0.22 * (1.0 - contrast))
    fg = principled_material("moonrise foreground silhouette", (dark, dark * 1.04, dark * 1.20, 1.0), roughness=0.96)
    _cube("moonrise horizon land mass", (0.0, 1.95, 0.10 + settings.horizon_height * 0.12), (4.1, 0.24, settings.horizon_height), fg)
    for index, x in enumerate((-2.35, -1.68, -0.92, -0.18, 0.54, 1.24, 2.04)):
        height = 0.22 + 0.18 * ((index % 4) / 3)
        _cube(f"moonrise foreground scale marker {index}", (x, 1.36 + index * 0.02, 0.16 + height * 0.5), (0.10, 0.10, height), fg, rotation=(0.0, 0.0, math.radians(index * 5.0)))


def _add_trail(settings: LongExposureMoonriseSettings) -> None:
    import bpy

    start, end = _trail_points(settings)
    color = _moon_color(settings)
    core = emission_material("moon trail bright core", color, settings.core_strength)
    halo = transparent_emission_material("moon trail soft halo", color, settings.halo_strength, min(0.58, 0.16 + settings.halo_strength * 0.18))
    if settings.halo_radius > 0:
        _curve("long exposure moon trail halo", [start, end], settings.halo_radius, halo)
    _curve("long exposure moon trail core", [start, end], settings.trail_thickness, core)

    terminal_color = _mix(color, (1.0, 0.96, 0.82, 1.0), 0.24)
    terminal = transparent_emission_material(
        "moon trail terminal glow",
        terminal_color,
        settings.core_strength * 0.84 + settings.halo_strength * 0.18,
        min(0.72, 0.24 + settings.terminal_softness * 1.2),
    )
    for index, point in enumerate((start, end)):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=0.06 + settings.terminal_softness, location=point)
        disk = bpy.context.object
        disk.name = f"moon trail terminal glow {index}"
        disk.scale.y = 0.10
        disk.data.materials.append(terminal)


def _add_lights(settings: LongExposureMoonriseSettings) -> None:
    import bpy

    color = _mix((0.30, 0.36, 0.58, 1.0), (0.82, 0.52, 0.32, 1.0), settings.moon_warmth)
    bpy.ops.object.light_add(type="AREA", location=(-2.8, -1.8, 2.0))
    fill = bpy.context.object
    fill.name = "very low moonrise fill"
    fill.data.energy = 28 + settings.sky_exposure * 54
    fill.data.size = 5.8
    fill.data.color = color[:3]
    look_at(fill, (0.0, 1.8, 0.42))


def _add_camera() -> None:
    add_orbit_camera(
        name=LONG_EXPOSURE_MOONRISE_CAMERA,
        target=(0.0, 2.08, 0.78),
        distance=4.9,
        lens_mm=60.0,
        yaw_degrees=0.0,
        pitch_degrees=2.8,
    )


def build_long_exposure_moonrise_scene(settings: LongExposureMoonriseSettings | Mapping[str, Any] | None = None) -> None:
    moonrise_settings = coerce_long_exposure_moonrise_settings(settings)
    clear_scene()
    _configure_world(moonrise_settings)
    _add_sky(moonrise_settings)
    _add_foreground(moonrise_settings)
    _add_trail(moonrise_settings)
    _add_lights(moonrise_settings)
    _add_camera()
