from __future__ import annotations

import dataclasses
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from blender_workbench.materials import principled_material, textured_transparent_emission_material, transparent_emission_material
from blender_workbench.presets import PLUME_ALPHA_STRENGTH, PLUME_SHAPE, two_axis_variants
from blender_workbench.sweep import SweepVariant, named_variants


ROCKET_PLUME_CAMERA = "rocket_plume_camera"


@dataclass(frozen=True)
class RocketPlumeSettings:
    """Procedural vacuum plume settings.

    The defaults aim for an optically thin, expanding upper-stage plume rather
    than a narrow orange torch. Keep this recipe fast enough for scouting
    sweeps while avoiding obviously ray-like diagnostic geometry.
    """

    shell_alpha: float = 0.026
    shell_strength: float = 0.42
    filament_alpha: float = 0.095
    filament_strength: float = 0.55
    filament_count: int = 18
    width: float = 1.45
    length: float = 1.12
    smoke_alpha: float = 0.034
    smoke_strength: float = 0.055
    billow_count: int = 12
    billow_jitter: float = 0.32
    plume_texture_magnitude: float = 0.08
    plume_texture_scale: float = 10.0
    billow_texture_magnitude: float = 0.12
    billow_texture_scale: float = 5.5
    density_ribbon_count: int = 6
    density_ribbon_alpha: float = 0.030
    density_ribbon_strength: float = 0.14
    density_ribbon_width: float = 0.36
    density_wisp_count: int = 34
    density_wisp_alpha: float = 0.048
    density_wisp_strength: float = 0.22
    density_wisp_radius: float = 0.009
    density_clump_count: int = 18
    density_clump_alpha: float = 0.032
    density_clump_strength: float = 0.055
    density_clump_scale: float = 0.46
    filament_wiggle: float = 0.24
    shell_rib_count: int = 6
    shell_rib_alpha: float = 0.030
    shell_rib_strength: float = 0.16
    core_alpha: float = 0.055
    core_strength: float = 0.48
    core_length: float = 0.28
    warmth: float = 0.025
    body_color: tuple[float, float, float, float] = (0.62, 0.66, 0.67, 1.0)
    shell_color: tuple[float, float, float, float] = (0.46, 0.56, 0.64, 1.0)
    filament_color: tuple[float, float, float, float] = (0.62, 0.76, 0.88, 1.0)
    smoke_color: tuple[float, float, float, float] = (0.38, 0.45, 0.50, 1.0)


def coerce_rocket_plume_settings(settings: RocketPlumeSettings | Mapping[str, Any] | None = None) -> RocketPlumeSettings:
    if isinstance(settings, RocketPlumeSettings):
        return settings
    data = dataclasses.asdict(RocketPlumeSettings())
    if settings:
        data.update({key: value for key, value in dict(settings).items() if key in data})
    return RocketPlumeSettings(**data)


def rocket_plume_scout_variants(*, prefix: str = "vacuum") -> list[SweepVariant]:
    variants = two_axis_variants(PLUME_ALPHA_STRENGTH, PLUME_SHAPE, prefix=prefix)
    return [
        SweepVariant(
            name=variant.name,
            label=variant.label,
            settings=variant.settings,
            note="alpha/strength x broad vacuum plume shape",
        )
        for variant in variants
    ]


def rocket_plume_texture_variants(*, prefix: str = "texture") -> list[SweepVariant]:
    return named_variants(
        {
            "smooth": {
                "plume_texture_magnitude": 0.0,
                "billow_texture_magnitude": 0.0,
                "density_ribbon_count": 0,
                "density_wisp_count": 0,
                "density_clump_count": 0,
                "filament_wiggle": 0.03,
                "shell_rib_count": 0,
                "billow_count": 6,
                "filament_count": 24,
            },
            "faint_ribs": {
                "plume_texture_magnitude": 0.02,
                "billow_texture_magnitude": 0.04,
                "density_ribbon_count": 5,
                "density_ribbon_alpha": 0.032,
                "density_ribbon_strength": 0.16,
                "density_wisp_count": 10,
                "density_wisp_alpha": 0.05,
                "density_wisp_strength": 0.22,
                "density_clump_count": 4,
                "filament_wiggle": 0.08,
                "shell_rib_count": 5,
                "billow_count": 7,
                "filament_count": 26,
            },
            "grain": {
                "plume_texture_magnitude": 0.05,
                "plume_texture_scale": 14.0,
                "billow_texture_magnitude": 0.08,
                "billow_texture_scale": 8.0,
                "density_ribbon_count": 7,
                "density_ribbon_alpha": 0.045,
                "density_ribbon_strength": 0.22,
                "density_wisp_count": 16,
                "density_wisp_alpha": 0.075,
                "density_wisp_strength": 0.34,
                "density_clump_count": 8,
                "density_clump_alpha": 0.045,
                "density_clump_strength": 0.09,
                "filament_wiggle": 0.12,
                "shell_rib_count": 8,
                "billow_count": 8,
                "filament_count": 30,
            },
            "grain_wide": {
                "plume_texture_magnitude": 0.06,
                "plume_texture_scale": 10.0,
                "billow_texture_magnitude": 0.10,
                "density_ribbon_count": 9,
                "density_ribbon_alpha": 0.052,
                "density_ribbon_strength": 0.26,
                "density_ribbon_width": 0.30,
                "density_wisp_count": 18,
                "density_wisp_alpha": 0.08,
                "density_wisp_strength": 0.36,
                "density_clump_count": 10,
                "density_clump_alpha": 0.052,
                "density_clump_strength": 0.11,
                "density_clump_scale": 0.42,
                "filament_wiggle": 0.14,
                "shell_rib_count": 10,
                "billow_count": 9,
                "billow_jitter": 0.30,
                "filament_count": 32,
            },
            "billowy": {
                "plume_texture_magnitude": 0.10,
                "plume_texture_scale": 6.5,
                "billow_texture_magnitude": 0.16,
                "billow_texture_scale": 3.2,
                "density_ribbon_count": 12,
                "density_ribbon_alpha": 0.065,
                "density_ribbon_strength": 0.34,
                "density_ribbon_width": 0.34,
                "density_wisp_count": 30,
                "density_wisp_alpha": 0.095,
                "density_wisp_strength": 0.44,
                "density_wisp_radius": 0.016,
                "density_clump_count": 18,
                "density_clump_alpha": 0.062,
                "density_clump_strength": 0.13,
                "density_clump_scale": 0.48,
                "filament_wiggle": 0.24,
                "shell_rib_count": 14,
                "billow_count": 13,
                "billow_jitter": 0.38,
                "filament_count": 38,
            },
            "billow_bands": {
                "plume_texture_magnitude": 0.12,
                "plume_texture_scale": 5.2,
                "billow_texture_magnitude": 0.18,
                "billow_texture_scale": 2.8,
                "density_ribbon_count": 16,
                "density_ribbon_alpha": 0.072,
                "density_ribbon_strength": 0.40,
                "density_ribbon_width": 0.46,
                "density_wisp_count": 22,
                "density_wisp_alpha": 0.09,
                "density_wisp_strength": 0.42,
                "density_wisp_radius": 0.014,
                "density_clump_count": 24,
                "density_clump_alpha": 0.07,
                "density_clump_strength": 0.15,
                "density_clump_scale": 0.58,
                "filament_wiggle": 0.20,
                "shell_rib_count": 12,
                "billow_count": 18,
                "billow_jitter": 0.44,
                "filament_count": 34,
            },
            "wispy": {
                "plume_texture_magnitude": 0.12,
                "plume_texture_scale": 12.0,
                "billow_texture_magnitude": 0.12,
                "density_ribbon_count": 8,
                "density_ribbon_alpha": 0.05,
                "density_ribbon_strength": 0.30,
                "density_wisp_count": 52,
                "density_wisp_alpha": 0.10,
                "density_wisp_strength": 0.56,
                "density_wisp_radius": 0.014,
                "density_clump_count": 8,
                "filament_wiggle": 0.34,
                "shell_rib_count": 18,
                "billow_count": 9,
                "filament_count": 58,
            },
            "ribbed": {
                "plume_texture_magnitude": 0.08,
                "billow_texture_magnitude": 0.10,
                "density_ribbon_count": 26,
                "density_ribbon_alpha": 0.082,
                "density_ribbon_strength": 0.54,
                "density_ribbon_width": 0.34,
                "density_wisp_count": 28,
                "density_wisp_alpha": 0.10,
                "density_wisp_strength": 0.48,
                "density_clump_count": 10,
                "shell_rib_count": 34,
                "shell_rib_alpha": 0.08,
                "shell_rib_strength": 0.48,
                "filament_wiggle": 0.30,
                "billow_count": 10,
                "filament_count": 44,
            },
            "shredded": {
                "plume_texture_magnitude": 0.18,
                "plume_texture_scale": 18.0,
                "billow_texture_magnitude": 0.24,
                "billow_texture_scale": 2.4,
                "density_ribbon_count": 18,
                "density_ribbon_alpha": 0.085,
                "density_ribbon_strength": 0.48,
                "density_ribbon_width": 0.48,
                "density_wisp_count": 48,
                "density_wisp_alpha": 0.13,
                "density_wisp_strength": 0.62,
                "density_wisp_radius": 0.019,
                "density_clump_count": 24,
                "density_clump_alpha": 0.08,
                "density_clump_strength": 0.18,
                "density_clump_scale": 0.54,
                "filament_wiggle": 0.42,
                "shell_rib_count": 22,
                "billow_count": 18,
                "billow_jitter": 0.52,
                "filament_count": 54,
            },
            "shred_wide": {
                "plume_texture_magnitude": 0.20,
                "plume_texture_scale": 10.0,
                "billow_texture_magnitude": 0.24,
                "density_ribbon_count": 20,
                "density_ribbon_alpha": 0.09,
                "density_ribbon_strength": 0.54,
                "density_ribbon_width": 0.62,
                "density_wisp_count": 56,
                "density_wisp_alpha": 0.14,
                "density_wisp_strength": 0.68,
                "density_wisp_radius": 0.020,
                "density_clump_count": 30,
                "density_clump_alpha": 0.09,
                "density_clump_strength": 0.20,
                "density_clump_scale": 0.66,
                "filament_wiggle": 0.46,
                "shell_rib_count": 20,
                "billow_count": 22,
                "billow_jitter": 0.62,
                "filament_count": 56,
            },
            "lace": {
                "plume_texture_magnitude": 0.22,
                "plume_texture_scale": 28.0,
                "billow_texture_magnitude": 0.18,
                "density_ribbon_count": 10,
                "density_ribbon_alpha": 0.06,
                "density_ribbon_strength": 0.38,
                "density_wisp_count": 92,
                "density_wisp_alpha": 0.16,
                "density_wisp_strength": 0.82,
                "density_wisp_radius": 0.012,
                "density_clump_count": 12,
                "filament_wiggle": 0.56,
                "shell_rib_count": 24,
                "billow_count": 10,
                "filament_count": 78,
            },
            "storm": {
                "plume_texture_magnitude": 0.24,
                "plume_texture_scale": 6.0,
                "billow_texture_magnitude": 0.30,
                "billow_texture_scale": 2.2,
                "density_ribbon_count": 24,
                "density_ribbon_alpha": 0.10,
                "density_ribbon_strength": 0.62,
                "density_ribbon_width": 0.70,
                "density_wisp_count": 42,
                "density_wisp_alpha": 0.13,
                "density_wisp_strength": 0.64,
                "density_clump_count": 44,
                "density_clump_alpha": 0.10,
                "density_clump_strength": 0.24,
                "density_clump_scale": 0.76,
                "filament_wiggle": 0.50,
                "shell_rib_count": 18,
                "billow_count": 28,
                "billow_jitter": 0.74,
                "filament_count": 50,
            },
            "overdone": {
                "plume_texture_magnitude": 0.30,
                "plume_texture_scale": 24.0,
                "billow_texture_magnitude": 0.30,
                "billow_texture_scale": 10.0,
                "density_ribbon_count": 30,
                "density_ribbon_alpha": 0.12,
                "density_ribbon_strength": 0.72,
                "density_ribbon_width": 0.72,
                "density_wisp_count": 84,
                "density_wisp_alpha": 0.18,
                "density_wisp_strength": 0.92,
                "density_wisp_radius": 0.024,
                "density_clump_count": 36,
                "density_clump_alpha": 0.11,
                "density_clump_strength": 0.28,
                "density_clump_scale": 0.72,
                "filament_wiggle": 0.68,
                "shell_rib_count": 34,
                "billow_count": 22,
                "billow_jitter": 0.75,
                "filament_count": 72,
            },
            "over_lace": {
                "plume_texture_magnitude": 0.34,
                "plume_texture_scale": 32.0,
                "billow_texture_magnitude": 0.26,
                "density_ribbon_count": 22,
                "density_ribbon_alpha": 0.10,
                "density_ribbon_strength": 0.66,
                "density_wisp_count": 110,
                "density_wisp_alpha": 0.19,
                "density_wisp_strength": 1.0,
                "density_wisp_radius": 0.018,
                "density_clump_count": 24,
                "density_clump_alpha": 0.09,
                "density_clump_strength": 0.20,
                "filament_wiggle": 0.78,
                "shell_rib_count": 38,
                "billow_count": 16,
                "filament_count": 96,
            },
            "over_cloud": {
                "plume_texture_magnitude": 0.28,
                "plume_texture_scale": 8.0,
                "billow_texture_magnitude": 0.40,
                "billow_texture_scale": 2.0,
                "density_ribbon_count": 32,
                "density_ribbon_alpha": 0.13,
                "density_ribbon_strength": 0.76,
                "density_ribbon_width": 0.84,
                "density_wisp_count": 50,
                "density_wisp_alpha": 0.15,
                "density_wisp_strength": 0.74,
                "density_clump_count": 58,
                "density_clump_alpha": 0.13,
                "density_clump_strength": 0.34,
                "density_clump_scale": 0.86,
                "filament_wiggle": 0.62,
                "shell_rib_count": 26,
                "billow_count": 34,
                "billow_jitter": 0.84,
                "filament_count": 68,
            },
            "whiteout_fail": {
                "plume_texture_magnitude": 0.45,
                "plume_texture_scale": 18.0,
                "billow_texture_magnitude": 0.52,
                "billow_texture_scale": 5.0,
                "density_ribbon_count": 44,
                "density_ribbon_alpha": 0.20,
                "density_ribbon_strength": 1.15,
                "density_ribbon_width": 1.0,
                "density_wisp_count": 130,
                "density_wisp_alpha": 0.27,
                "density_wisp_strength": 1.25,
                "density_wisp_radius": 0.028,
                "density_clump_count": 72,
                "density_clump_alpha": 0.20,
                "density_clump_strength": 0.48,
                "density_clump_scale": 0.98,
                "filament_wiggle": 0.86,
                "shell_rib_count": 48,
                "billow_count": 44,
                "billow_jitter": 0.92,
                "filament_count": 112,
            },
        },
        prefix=prefix,
        note="rocket plume texture stride scout",
        roles={
            "smooth": "baseline",
            "overdone": "aesthetic_extreme",
            "over_lace": "aesthetic_extreme",
            "over_cloud": "aesthetic_extreme",
            "whiteout_fail": "failure_anchor",
        },
        tags_by_name={
            "smooth": ("texture_baseline",),
            "overdone": ("texture_extreme",),
            "over_lace": ("texture_extreme",),
            "over_cloud": ("texture_extreme",),
            "whiteout_fail": ("whiteout", "too_far"),
        },
    )


def clear_scene() -> None:
    import bpy

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def look_at(obj: Any, target: tuple[float, float, float]) -> None:
    from mathutils import Vector

    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def _shade_smooth() -> None:
    import bpy

    try:
        bpy.ops.object.shade_smooth()
    except RuntimeError:
        pass


def open_cone(name: str, start, end, r1: float, r2: float, mat: Any, *, vertices: int = 72) -> Any:
    import bpy
    from mathutils import Vector

    start_v = Vector(start)
    end_v = Vector(end)
    mid = (start_v + end_v) * 0.5
    bpy.ops.mesh.primitive_cone_add(
        vertices=vertices,
        radius1=r1,
        radius2=r2,
        depth=(end_v - start_v).length,
        end_fill_type="NOTHING",
        location=mid,
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.materials.append(mat)
    obj.rotation_euler = (end_v - start_v).to_track_quat("Z", "Y").to_euler()
    _shade_smooth()
    return obj


def filament_curve(name: str, points: list[tuple[float, float, float]], radius: float, mat: Any) -> Any:
    import bpy

    curve = bpy.data.curves.new(name, type="CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 2
    curve.bevel_depth = radius
    curve.bevel_resolution = 2
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for point, co in zip(spline.points, points, strict=True):
        point.co = (co[0], co[1], co[2], 1.0)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    return obj


def _smoothstep(value: float) -> float:
    t = max(0.0, min(1.0, value))
    return t * t * (3.0 - 2.0 * t)


def _plume_radius(settings: RocketPlumeSettings, t: float, *, phase: float = 0.0) -> float:
    """Approximate the fast radial expansion of an upper-stage vacuum plume."""

    clamped = max(0.0, min(1.0, t))
    expansion = 1.0 - math.exp(-3.4 * clamped)
    waviness = 1.0 + 0.045 * math.sin(phase + clamped * math.pi * 2.2)
    return settings.width * (0.10 + 1.58 * expansion) * waviness


def _plume_point(
    settings: RocketPlumeSettings,
    throat: tuple[float, float, float],
    end_x: float,
    t: float,
    angle: float,
    radial_fraction: float,
    *,
    phase: float = 0.0,
) -> tuple[float, float, float]:
    radius = _plume_radius(settings, t, phase=phase) * radial_fraction
    return (
        throat[0] + (end_x - throat[0]) * t,
        math.sin(angle) * radius,
        math.cos(angle * 0.87 + phase * 0.18) * radius * 0.56,
    )


def density_ribbon(name: str, throat: tuple[float, float, float], end_x: float, radius: float, angle: float, width: float, mat: Any) -> Any:
    import bpy

    def rim(theta: float, scale: float = 1.0) -> tuple[float, float, float]:
        return (
            end_x,
            math.sin(theta) * radius * scale,
            math.cos(theta * 0.86) * radius * 0.56 * scale,
        )

    start_x = throat[0] + (end_x - throat[0]) * 0.14
    mid_x = throat[0] + (end_x - throat[0]) * 0.52
    start_radius = radius * 0.10
    mid_radius = radius * 0.42
    verts = [
        (start_x, math.sin(angle - width * 0.18) * start_radius, math.cos(angle) * start_radius * 0.44),
        (mid_x, math.sin(angle - width * 0.42) * mid_radius, math.cos(angle * 0.94) * mid_radius * 0.44),
        rim(angle - width),
        rim(angle + width),
        (mid_x, math.sin(angle + width * 0.42) * mid_radius, math.cos(angle * 0.82) * mid_radius * 0.44),
        (start_x, math.sin(angle + width * 0.18) * start_radius, math.cos(angle * 0.88) * start_radius * 0.44),
    ]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], [(0, 1, 5), (1, 4, 5), (1, 2, 3), (1, 3, 4)])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    return obj


def _add_rocket_body(settings: RocketPlumeSettings) -> None:
    import bpy

    body = principled_material("rocket body", settings.body_color, roughness=0.62, metallic=0.08)
    nozzle = principled_material("dark engine bell", (0.025, 0.024, 0.028, 1), roughness=0.45, metallic=0.45)

    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=0.28, depth=2.55, location=(-1.22, 0, 0), rotation=(0, math.pi / 2, 0))
    bpy.context.object.name = "upper stage body"
    bpy.context.object.data.materials.append(body)
    _shade_smooth()

    bpy.ops.mesh.primitive_cone_add(vertices=56, radius1=0.28, radius2=0.09, depth=0.58, location=(0.12, 0, 0), rotation=(0, math.pi / 2, 0))
    bpy.context.object.name = "engine bell"
    bpy.context.object.data.materials.append(nozzle)
    _shade_smooth()


def _add_plume(settings: RocketPlumeSettings) -> None:
    import bpy

    warm_shell = (
        min(1.0, settings.shell_color[0] + settings.warmth),
        min(1.0, settings.shell_color[1] + settings.warmth * 0.35),
        max(0.0, settings.shell_color[2] - settings.warmth * 0.25),
        1.0,
    )
    shell = textured_transparent_emission_material(
        "translucent plume shell",
        warm_shell,
        settings.shell_strength,
        settings.shell_alpha,
        texture_magnitude=settings.plume_texture_magnitude,
        texture_scale=settings.plume_texture_scale,
    )
    filament = transparent_emission_material("blue plume filaments", settings.filament_color, settings.filament_strength, settings.filament_alpha)
    rib = transparent_emission_material("plume shell ribs", settings.filament_color, settings.shell_rib_strength, settings.shell_rib_alpha)
    density = transparent_emission_material("spatial plume density", settings.smoke_color, settings.density_ribbon_strength, settings.density_ribbon_alpha)
    wisp = transparent_emission_material("thin density wisps", settings.filament_color, settings.density_wisp_strength, settings.density_wisp_alpha)
    clump = transparent_emission_material("soft density clumps", settings.smoke_color, settings.density_clump_strength, settings.density_clump_alpha)
    smoke = textured_transparent_emission_material(
        "gray blue billow shell",
        settings.smoke_color,
        settings.smoke_strength,
        settings.smoke_alpha,
        texture_magnitude=settings.billow_texture_magnitude,
        texture_scale=settings.billow_texture_scale,
    )
    core = transparent_emission_material("short bright engine core", (0.72, 0.88, 1.0, 1), settings.core_strength, settings.core_alpha)

    throat = (0.26, 0.0, 0.0)
    plume_end_x = 4.7 * settings.length
    open_cone("short non-flame engine core", throat, (0.68 + settings.core_length, 0, 0), 0.050, 0.18 * settings.width, core, vertices=48)

    for index, scale in enumerate([0.56, 0.82, 1.08]):
        t_end = 0.78 + index * 0.08
        end_radius = _plume_radius(settings, t_end, phase=index * 0.6) * scale
        end = (
            plume_end_x * t_end,
            math.sin(index * 1.9) * 0.05 * settings.width,
            math.cos(index * 1.4) * 0.03 * settings.width,
        )
        open_cone(
            f"nested plume shell {index}",
            throat,
            end,
            0.07 + index * 0.012,
            end_radius,
            shell,
            vertices=96,
        )

    for index in range(max(0, int(settings.density_ribbon_count))):
        frac = (index + 0.5) / max(1, settings.density_ribbon_count)
        angle = index * 2.618 + math.sin(index * 0.71) * 0.34
        t_end = 0.44 + 0.42 * _smoothstep(frac)
        density_ribbon(
            f"density ribbon {index:02d}",
            throat,
            plume_end_x * t_end,
            _plume_radius(settings, t_end, phase=angle) * (0.56 + 0.24 * math.sin(index * 0.57) ** 2),
            angle,
            settings.density_ribbon_width * (0.8 + 0.9 * frac),
            density,
        )

    for index in range(max(0, int(settings.shell_rib_count))):
        frac = (index + 0.5) / max(1, settings.shell_rib_count)
        angle = index * 2.399
        t0 = 0.08
        t1 = 0.30 + 0.10 * math.sin(index * 0.67) ** 2
        t2 = 0.58 + 0.18 * frac
        t3 = 0.82 + 0.08 * math.sin(index * 0.47) ** 2
        points = [
            _plume_point(settings, throat, plume_end_x, t0, angle, 0.10, phase=index),
            _plume_point(settings, throat, plume_end_x, t1, angle + 0.12, 0.34, phase=index),
            _plume_point(settings, throat, plume_end_x, t2, angle + 0.26, 0.62 + 0.20 * frac, phase=index),
            _plume_point(settings, throat, plume_end_x, t3, angle + 0.34, 0.82 + 0.10 * frac, phase=index),
        ]
        filament_curve(f"shell rib {index:02d}", points, 0.003 + 0.002 * (1.0 - frac), rib)

    for index in range(max(0, int(settings.density_wisp_count))):
        frac = (index + 0.5) / max(1, settings.density_wisp_count)
        angle = index * 2.177
        start_t = 0.14 + 0.10 * math.sin(index * 1.13) ** 2
        mid_t = 0.34 + 0.22 * frac
        end_t = 0.56 + 0.36 * _smoothstep(frac)
        radial = 0.18 + 0.56 * frac
        points = [
            _plume_point(settings, throat, plume_end_x, start_t, angle, radial * 0.25, phase=index),
            _plume_point(settings, throat, plume_end_x, mid_t, angle + 0.30 * math.sin(index), radial * 0.55, phase=index),
            _plume_point(settings, throat, plume_end_x, (mid_t + end_t) * 0.5, angle + 0.46, radial * 0.78, phase=index),
            _plume_point(settings, throat, plume_end_x, end_t, angle + 0.70, radial * (0.88 + 0.12 * math.sin(index * 0.37)), phase=index),
        ]
        filament_curve(f"density wisp {index:02d}", points, settings.density_wisp_radius * (0.55 + 0.55 * (1.0 - frac)), wisp)

    for index in range(settings.billow_count):
        t = (index + 0.8) / (settings.billow_count + 1.0)
        phase = index * 2.399
        radius = _plume_radius(settings, t, phase=phase) * (1.0 + 0.18 * settings.billow_texture_magnitude * math.sin(index * 1.71))
        x = throat[0] + (plume_end_x - throat[0]) * (0.12 + 0.82 * t)
        y = math.sin(phase) * radius * settings.billow_jitter * (0.24 + 0.52 * t)
        z = math.cos(phase * 0.73) * radius * settings.billow_jitter * (0.18 + 0.34 * t)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=1.0, location=(x, y, z))
        obj = bpy.context.object
        obj.name = f"soft billow {index:02d}"
        lump = 1.0 + settings.billow_texture_magnitude * 0.24 * math.sin(index * 2.17)
        obj.scale = ((0.14 + 0.26 * t) * lump, radius * 0.34, radius * 0.24 * (2.0 - lump))
        obj.data.materials.append(smoke)
        _shade_smooth()

    for index in range(max(0, int(settings.density_clump_count))):
        frac = (index + 0.5) / max(1, settings.density_clump_count)
        phase = index * 2.071
        t = 0.20 + 0.66 * _smoothstep(frac)
        radius = _plume_radius(settings, t, phase=phase)
        x = throat[0] + (plume_end_x - throat[0]) * t
        y = math.sin(phase) * radius * (0.12 + 0.26 * math.sin(index * 0.59) ** 2)
        z = math.cos(phase * 0.81) * radius * (0.14 + 0.18 * frac)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=1.0, location=(x, y, z))
        obj = bpy.context.object
        obj.name = f"density clump {index:02d}"
        scale = settings.density_clump_scale * (0.34 + 0.62 * frac)
        obj.scale = (scale * 0.45, scale * (0.64 + 0.30 * math.sin(index)), scale * 0.38)
        obj.data.materials.append(clump)
        _shade_smooth()

    count = max(0, int(settings.filament_count))
    for index in range(count):
        frac = (index + 0.5) / max(1, count)
        angle = index * 2.618
        wiggle = settings.filament_wiggle
        radial = 0.22 + 0.72 * frac
        t0 = 0.04 + 0.03 * math.sin(index * 0.61) ** 2
        t1 = 0.22 + 0.08 * math.sin(index * 1.23) ** 2
        t2 = 0.50 + 0.18 * frac
        t3 = 0.72 + 0.18 * math.sin(index * 0.71) ** 2
        points = [
            _plume_point(settings, throat, plume_end_x, t0, angle, 0.06, phase=index),
            _plume_point(settings, throat, plume_end_x, t1, angle + 0.18, radial * 0.26, phase=index + wiggle),
            _plume_point(settings, throat, plume_end_x, t2, angle + 0.42 + math.sin(index * 3.1) * wiggle * 0.18, radial * 0.58, phase=index),
            _plume_point(settings, throat, plume_end_x, t3, angle + 0.76 + math.cos(index * 2.7) * wiggle * 0.14, radial, phase=index),
        ]
        radius = 0.0032 + 0.0038 * (1.0 - frac)
        filament_curve(f"plume filament {index:02d}", points, radius, filament)


def _add_camera_and_light() -> None:
    import bpy

    world = bpy.context.scene.world or bpy.data.worlds.new("rocket plume world")
    bpy.context.scene.world = world
    world.color = (0.005, 0.006, 0.008)

    bpy.ops.object.light_add(type="AREA", location=(-2.4, -3.6, 2.4))
    key = bpy.context.object
    key.name = "cool rim area"
    key.data.energy = 260
    key.data.size = 4.0

    bpy.ops.object.light_add(type="SUN", location=(0, 0, 0))
    sun = bpy.context.object
    sun.name = "weak orbital sun"
    sun.data.energy = 0.28
    sun.rotation_euler = (0.6, 0.25, -0.45)

    bpy.ops.object.camera_add(location=(2.3, -6.6, 1.05))
    cam = bpy.context.object
    cam.name = ROCKET_PLUME_CAMERA
    look_at(cam, (2.25, 0.0, 0.05))
    cam.data.lens = 46
    bpy.context.scene.camera = cam


def build_rocket_plume_scene(settings: RocketPlumeSettings | Mapping[str, Any] | None = None) -> None:
    """Build a fast diagnostic scene for vacuum-plume sweep work."""

    plume_settings = coerce_rocket_plume_settings(settings)
    clear_scene()
    _add_rocket_body(plume_settings)
    _add_plume(plume_settings)
    _add_camera_and_light()
