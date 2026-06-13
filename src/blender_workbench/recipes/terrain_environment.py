from __future__ import annotations

import dataclasses
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from blender_workbench.camera import add_orbit_camera, look_at
from blender_workbench.materials import emission_material, principled_material
from blender_workbench.sweep import SweepVariant


TERRAIN_ENVIRONMENT_CAMERA = "terrain_environment_camera"


@dataclass(frozen=True)
class TerrainEnvironmentSettings:
    terrain_relief: float = 0.42
    ridge_frequency: float = 2.6
    erosion: float = 0.32
    band_contrast: float = 0.58
    band_warp: float = 0.55
    warm_bias: float = 0.42
    haze_alpha: float = 0.20
    horizon_glow: float = 0.45
    sun_angle: float = -18.0
    sun_energy: float = 540.0
    sun_warmth: float = 0.72
    foreground_scale: float = 1.0
    foreground_count: int = 8


def coerce_terrain_environment_settings(
    settings: TerrainEnvironmentSettings | Mapping[str, Any] | None = None,
) -> TerrainEnvironmentSettings:
    if isinstance(settings, TerrainEnvironmentSettings):
        return settings
    data = dataclasses.asdict(TerrainEnvironmentSettings())
    if settings:
        data.update({key: value for key, value in dict(settings).items() if key in data})
    return TerrainEnvironmentSettings(**data)


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


def _scale_color(color: tuple[float, float, float, float], amount: float) -> tuple[float, float, float, float]:
    return (_clamp(color[0] * amount, 0.0, 1.0), _clamp(color[1] * amount, 0.0, 1.0), _clamp(color[2] * amount, 0.0, 1.0), color[3])


def terrain_environment_variants(
    *,
    prefix: str = "terrain",
    steps: tuple[int, ...] = (-2, -1, 0, 1, 2),
    relief_stride: float = 0.24,
    band_stride: float = 0.28,
    haze_stride: float = 0.13,
    light_stride: float = 18.0,
    foreground_stride: float = 0.34,
) -> list[SweepVariant]:
    """Build a same-view stride board for stylized landscape environments."""
    base = dataclasses.asdict(TerrainEnvironmentSettings())
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
                note="same-view environment scout: relief, strata, haze, backlight, foreground",
            )
        )

    for step in steps:
        add(
            f"relief_{_step_label(step)}",
            {
                "terrain_relief": _clamp(0.42 + step * relief_stride, 0.04, 1.05),
                "ridge_frequency": _clamp(2.6 + step * 0.55, 0.9, 5.0),
                "erosion": _clamp(0.32 + step * 0.10, 0.04, 0.72),
            },
        )

    for step in steps:
        add(
            f"strata_{_step_label(step)}",
            {
                "band_contrast": _clamp(0.58 + step * band_stride, 0.08, 1.35),
                "band_warp": _clamp(0.55 + step * 0.25, 0.02, 1.25),
                "warm_bias": _clamp(0.42 + step * 0.11, 0.04, 0.86),
            },
        )

    for step in steps:
        add(
            f"haze_{_step_label(step)}",
            {
                "haze_alpha": _clamp(0.20 + step * haze_stride, 0.0, 0.62),
                "horizon_glow": _clamp(0.45 + step * 0.18, 0.02, 1.0),
            },
        )

    for step in steps:
        add(
            f"light_{_step_label(step)}",
            {
                "sun_angle": _clamp(-18.0 + step * light_stride, -64.0, 42.0),
                "sun_energy": _clamp(540.0 + step * 145.0, 160.0, 980.0),
                "sun_warmth": _clamp(0.72 + step * 0.10, 0.28, 1.0),
            },
        )

    for step in steps:
        add(
            f"fg_{_step_label(step)}",
            {
                "foreground_scale": _clamp(1.0 + step * foreground_stride, 0.28, 1.9),
                "foreground_count": max(2, min(14, round(8 + step * 2))),
            },
        )

    return variants


def clear_scene() -> None:
    import bpy

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def _terrain_height(x: float, y: float, settings: TerrainEnvironmentSettings) -> float:
    relief = settings.terrain_relief
    ridges = math.sin(y * settings.ridge_frequency + x * 0.42) * 0.45
    broad = math.sin(y * 0.86 - x * 1.35) * 0.28
    broken = math.sin((x * 2.9 + y * 1.7) * (0.7 + settings.erosion)) * 0.14
    slope = -0.08 * y + 0.025 * abs(x)
    return relief * (ridges + broad + broken) + slope


def _terrain_materials(settings: TerrainEnvironmentSettings) -> list[Any]:
    cool = (0.24, 0.33, 0.42, 1.0)
    warm = (0.66, 0.42, 0.28, 1.0)
    pale = (0.70, 0.70, 0.62, 1.0)
    rust = (0.48, 0.18, 0.12, 1.0)
    bias = settings.warm_bias
    base_colors = (
        _mix(cool, warm, bias * 0.55),
        _mix(pale, warm, bias * 0.45),
        _mix(cool, rust, bias),
        _mix((0.14, 0.18, 0.22, 1.0), pale, bias * 0.34),
    )
    contrast = settings.band_contrast
    return [
        principled_material(f"terrain strata {index}", _scale_color(color, 0.62 + contrast * (0.18 + index * 0.12)), roughness=0.88)
        for index, color in enumerate(base_colors)
    ]


def _add_terrain(settings: TerrainEnvironmentSettings) -> None:
    import bpy

    cols = 40
    rows = 46
    width = 7.2
    y0 = -2.25
    y1 = 4.75
    verts = []
    for iy in range(rows + 1):
        y = y0 + (y1 - y0) * iy / rows
        for ix in range(cols + 1):
            x = -width * 0.5 + width * ix / cols
            verts.append((x, y, _terrain_height(x, y, settings)))

    faces = []
    stride = cols + 1
    for iy in range(rows):
        for ix in range(cols):
            a = iy * stride + ix
            faces.append((a, a + 1, a + stride + 1, a + stride))

    mesh = bpy.data.meshes.new("terrain environment mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new("low poly stratified terrain", mesh)
    bpy.context.scene.collection.objects.link(obj)
    for mat in _terrain_materials(settings):
        obj.data.materials.append(mat)
    for poly in obj.data.polygons:
        y = sum(obj.data.vertices[index].co.y for index in poly.vertices) / len(poly.vertices)
        z = sum(obj.data.vertices[index].co.z for index in poly.vertices) / len(poly.vertices)
        band = int(abs((y * 1.35 + z * settings.band_warp * 7.0) * (1.0 + settings.band_contrast * 0.42))) % len(obj.data.materials)
        poly.material_index = band
        poly.use_smooth = False


def _add_sky_and_haze(settings: TerrainEnvironmentSettings) -> None:
    import bpy

    sky = principled_material("cold europa sky", (0.055, 0.075, 0.105, 1.0), roughness=1.0)
    glow_color = _mix((0.50, 0.62, 1.0, 1.0), (1.0, 0.54, 0.22, 1.0), settings.sun_warmth)
    glow = emission_material("horizon glow band", glow_color, 0.18 + settings.horizon_glow * 0.65)
    sun = emission_material("small low sun disk", glow_color, 1.8 + settings.horizon_glow * 2.2)

    bpy.ops.mesh.primitive_plane_add(size=8.2, location=(0, 5.05, 1.75), rotation=(math.pi / 2, 0, 0))
    sky_obj = bpy.context.object
    sky_obj.name = "flat distant sky plane"
    sky_obj.scale.z = 0.65
    sky_obj.data.materials.append(sky)

    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 4.98, 0.72))
    glow_obj = bpy.context.object
    glow_obj.name = "low horizon glow strip"
    glow_obj.scale = (4.2, 0.018, 0.24 + settings.horizon_glow * 0.22)
    glow_obj.data.materials.append(glow)

    sun_x = math.sin(math.radians(settings.sun_angle)) * 2.4
    sun_z = 0.93 + math.cos(math.radians(settings.sun_angle)) * 0.22
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=0.16, location=(sun_x, 4.82, sun_z))
    sun_obj = bpy.context.object
    sun_obj.name = "low horizon sun disk"
    sun_obj.scale.y = 0.12
    sun_obj.data.materials.append(sun)


def _configure_world(settings: TerrainEnvironmentSettings) -> None:
    import bpy

    world = bpy.context.scene.world or bpy.data.worlds.new("terrain environment world")
    bpy.context.scene.world = world
    world.use_nodes = True
    nodes = world.node_tree.nodes
    nodes.clear()
    bg = nodes.new(type="ShaderNodeBackground")
    bg.inputs["Color"].default_value = (0.018, 0.022, 0.033, 1.0)
    bg.inputs["Strength"].default_value = 0.12 + settings.horizon_glow * 0.08
    volume = nodes.new(type="ShaderNodeVolumePrincipled")
    volume.inputs["Color"].default_value = _mix((0.36, 0.42, 0.62, 1.0), (0.82, 0.58, 0.50, 1.0), settings.sun_warmth)
    volume.inputs["Density"].default_value = settings.haze_alpha * 0.018
    out = nodes.new(type="ShaderNodeOutputWorld")
    world.node_tree.links.new(bg.outputs["Background"], out.inputs["Surface"])
    world.node_tree.links.new(volume.outputs["Volume"], out.inputs["Volume"])


def _add_foreground(settings: TerrainEnvironmentSettings) -> None:
    import bpy

    dark = principled_material("dark foreground stone", (0.08, 0.075, 0.085, 1.0), roughness=0.92)
    count = int(settings.foreground_count)
    for index in range(count):
        t = index / max(1, count - 1)
        x = -2.8 + t * 5.6
        y = -1.72 + 0.18 * math.sin(index * 1.8)
        z = _terrain_height(x, y, settings) + 0.10
        radius = (0.11 + 0.12 * (0.5 + 0.5 * math.sin(index * 2.1))) * settings.foreground_scale
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=radius, location=(x, y, z + radius * 0.55))
        rock = bpy.context.object
        rock.name = f"foreground rock {index:02d}"
        rock.scale = (1.45, 0.82, 0.55 + 0.4 * ((index % 3) / 2))
        rock.rotation_euler = (0.0, 0.0, index * 0.47)
        rock.data.materials.append(dark)


def _add_lights(settings: TerrainEnvironmentSettings) -> None:
    import bpy

    color = _mix((0.42, 0.52, 1.0, 1.0), (1.0, 0.56, 0.24, 1.0), settings.sun_warmth)
    angle = math.radians(settings.sun_angle)
    bpy.ops.object.light_add(type="AREA", location=(math.sin(angle) * 3.2, -2.2, 2.4 + math.cos(angle) * 0.4))
    key = bpy.context.object
    key.name = "low environment backlight"
    key.data.energy = settings.sun_energy
    key.data.size = 5.0
    key.data.color = color[:3]
    look_at(key, (0.0, 2.4, 0.35))

    bpy.ops.object.light_add(type="POINT", location=(-2.2, -1.8, 1.4))
    fill = bpy.context.object
    fill.name = "cold foreground fill"
    fill.data.energy = 38
    fill.data.color = (0.30, 0.40, 0.72)


def _add_camera() -> None:
    add_orbit_camera(
        name=TERRAIN_ENVIRONMENT_CAMERA,
        target=(0.0, 1.35, 0.48),
        distance=6.0,
        lens_mm=46.0,
        yaw_degrees=0.0,
        pitch_degrees=9.0,
    )


def build_terrain_environment_scene(settings: TerrainEnvironmentSettings | Mapping[str, Any] | None = None) -> None:
    import bpy

    terrain_settings = coerce_terrain_environment_settings(settings)
    clear_scene()
    _configure_world(terrain_settings)
    _add_terrain(terrain_settings)
    _add_sky_and_haze(terrain_settings)
    _add_foreground(terrain_settings)
    _add_lights(terrain_settings)
    _add_camera()
