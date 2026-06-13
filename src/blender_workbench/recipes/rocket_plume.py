from __future__ import annotations

import dataclasses
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from blender_workbench.materials import principled_material, transparent_emission_material
from blender_workbench.presets import PLUME_ALPHA_STRENGTH, PLUME_SHAPE, two_axis_variants
from blender_workbench.sweep import SweepVariant


ROCKET_PLUME_CAMERA = "rocket_plume_camera"


@dataclass(frozen=True)
class RocketPlumeSettings:
    """Cheap procedural vacuum plume settings.

    The defaults aim for a broad, smoky upper-stage plume rather than a narrow
    orange torch. Keep this recipe fast enough for scouting sweeps.
    """

    shell_alpha: float = 0.035
    shell_strength: float = 0.55
    filament_alpha: float = 0.18
    filament_strength: float = 0.85
    filament_count: int = 28
    width: float = 1.25
    length: float = 1.0
    smoke_alpha: float = 0.045
    smoke_strength: float = 0.08
    billow_count: int = 8
    billow_jitter: float = 0.22
    core_alpha: float = 0.08
    core_strength: float = 0.62
    core_length: float = 0.42
    warmth: float = 0.06
    body_color: tuple[float, float, float, float] = (0.62, 0.66, 0.67, 1.0)
    shell_color: tuple[float, float, float, float] = (0.50, 0.64, 0.78, 1.0)
    filament_color: tuple[float, float, float, float] = (0.58, 0.78, 1.0, 1.0)
    smoke_color: tuple[float, float, float, float] = (0.42, 0.50, 0.56, 1.0)


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
    shell = transparent_emission_material("translucent plume shell", warm_shell, settings.shell_strength, settings.shell_alpha)
    filament = transparent_emission_material("blue plume filaments", settings.filament_color, settings.filament_strength, settings.filament_alpha)
    smoke = transparent_emission_material("gray blue billow shell", settings.smoke_color, settings.smoke_strength, settings.smoke_alpha)
    core = transparent_emission_material("short bright engine core", (0.72, 0.88, 1.0, 1), settings.core_strength, settings.core_alpha)

    throat = (0.26, 0.0, 0.0)
    plume_end_x = 4.7 * settings.length
    open_cone("short non-flame engine core", throat, (0.75 + settings.core_length, 0, 0), 0.055, 0.28 * settings.width, core, vertices=48)

    for index, scale in enumerate([0.62, 0.9, 1.18]):
        end = (
            plume_end_x * (0.88 + index * 0.06),
            math.sin(index * 1.9) * 0.08 * settings.width,
            math.cos(index * 1.4) * 0.05 * settings.width,
        )
        open_cone(
            f"nested plume shell {index}",
            throat,
            end,
            0.10 + index * 0.015,
            (1.38 + index * 0.22) * settings.width * scale,
            shell,
            vertices=96,
        )

    for index in range(settings.billow_count):
        t = (index + 0.8) / (settings.billow_count + 1.0)
        phase = index * 2.399
        x = 0.55 + plume_end_x * t
        radius = (0.20 + 1.35 * t) * settings.width
        y = math.sin(phase) * radius * settings.billow_jitter
        z = math.cos(phase * 0.73) * radius * settings.billow_jitter * 0.62
        bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=1.0, location=(x, y, z))
        obj = bpy.context.object
        obj.name = f"soft billow {index:02d}"
        obj.scale = (0.18 + 0.35 * t, radius * 0.52, radius * 0.38)
        obj.data.materials.append(smoke)
        _shade_smooth()

    count = max(0, int(settings.filament_count))
    for index in range(count):
        frac = (index + 0.5) / max(1, count)
        angle = index * 2.618
        end_radius = settings.width * (0.35 + 1.35 * frac)
        end_x = plume_end_x * (0.78 + 0.2 * math.sin(index * 0.71) ** 2)
        end_y = math.sin(angle) * end_radius
        end_z = math.cos(angle * 0.83) * end_radius * 0.55
        mid_x = 0.55 + end_x * 0.45
        mid_y = end_y * (0.18 + 0.18 * math.sin(index * 0.37))
        mid_z = end_z * (0.12 + 0.16 * math.cos(index * 0.53))
        radius = 0.0045 + 0.006 * (1.0 - frac)
        filament_curve(f"plume filament {index:02d}", [throat, (mid_x, mid_y, mid_z), (end_x, end_y, end_z)], radius, filament)


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
