from __future__ import annotations

import dataclasses
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from blender_workbench.camera import add_orbit_camera, look_at
from blender_workbench.materials import emission_material, principled_material, transparent_emission_material
from blender_workbench.sweep import SweepVariant


CAUSTIC_WATER_CAMERA = "caustic_water_camera"


@dataclass(frozen=True)
class CausticWaterSettings:
    water_roughness: float = 0.045
    water_alpha: float = 0.32
    transmission_weight: float = 0.42
    caustic_scale: float = 8.0
    caustic_strength: float = 0.72
    caustic_contrast: float = 0.58
    light_size: float = 0.72
    light_distance: float = 2.2
    tint_strength: float = 0.26
    depth_marker_contrast: float = 0.74
    pattern_phase: float = 0.0


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


def coerce_caustic_water_settings(settings: CausticWaterSettings | Mapping[str, Any] | None = None) -> CausticWaterSettings:
    if isinstance(settings, CausticWaterSettings):
        return settings
    data = dataclasses.asdict(CausticWaterSettings())
    if settings:
        data.update({key: value for key, value in dict(settings).items() if key in data})
    return CausticWaterSettings(**data)


def caustic_water_descriptor(settings: CausticWaterSettings | Mapping[str, Any] | None = None) -> dict[str, Any]:
    caustic = coerce_caustic_water_settings(settings)
    return {
        "technique": "fake_procedural_caustic_ribbons",
        "physical_caustics": False,
        "water_roughness": _clamp(caustic.water_roughness, 0.0, 1.0),
        "caustic_scale": max(0.1, float(caustic.caustic_scale)),
        "caustic_strength": max(0.0, float(caustic.caustic_strength)),
        "caustic_contrast": _clamp01(caustic.caustic_contrast),
        "light_size": max(0.02, float(caustic.light_size)),
        "light_distance": max(0.2, float(caustic.light_distance)),
        "tint_strength": _clamp01(caustic.tint_strength),
        "diagnostics": ("structured_floor_grid", "background_value_steps", "water_sheet", "fake_caustic_ribbons"),
    }


def _variant_settings(overrides: Mapping[str, Any]) -> dict[str, Any]:
    data = dataclasses.asdict(CausticWaterSettings())
    data.update(dict(overrides))
    caustic = coerce_caustic_water_settings(data)
    payload = dataclasses.asdict(caustic)
    payload["caustic_water"] = caustic_water_descriptor(caustic)
    return payload


def caustic_water_variants(*, prefix: str = "caustic") -> list[SweepVariant]:
    cases: tuple[tuple[str, Mapping[str, Any]], ...] = (
        ("pool_balanced", {}),
        ("tight_ripples", {"caustic_scale": 18.0, "water_roughness": 0.018, "caustic_contrast": 0.72, "light_size": 0.34}),
        ("broad_pool", {"caustic_scale": 4.2, "water_roughness": 0.065, "caustic_contrast": 0.48, "light_size": 1.05}),
        ("soft_large_light", {"light_size": 1.8, "caustic_strength": 0.54, "caustic_contrast": 0.38, "water_roughness": 0.08}),
        ("small_hard_light", {"light_size": 0.18, "light_distance": 1.55, "caustic_strength": 0.92, "caustic_scale": 12.0}),
        ("blue_depth", {"tint_strength": 0.62, "water_alpha": 0.42, "depth_marker_contrast": 0.66}),
        ("clear_glass", {"water_alpha": 0.18, "transmission_weight": 0.68, "tint_strength": 0.10, "water_roughness": 0.012}),
        ("readable_floor", {"depth_marker_contrast": 0.92, "caustic_strength": 0.62, "caustic_contrast": 0.50}),
        ("zebra_fail", {"caustic_scale": 32.0, "water_roughness": 0.006, "caustic_strength": 1.35, "caustic_contrast": 0.96, "light_size": 0.08}),
        ("washed_blur_fail", {"caustic_scale": 2.2, "water_roughness": 0.22, "caustic_strength": 0.26, "caustic_contrast": 0.14, "light_size": 2.4}),
        ("blue_blob_fail", {"tint_strength": 0.92, "water_alpha": 0.70, "caustic_strength": 0.18, "depth_marker_contrast": 0.18}),
    )
    roles = {
        "pool_balanced": "baseline",
        "zebra_fail": "failure_anchor",
        "washed_blur_fail": "failure_anchor",
        "blue_blob_fail": "failure_anchor",
    }
    tags_by_label = {
        "zebra_fail": ("over_sharp", "zebra"),
        "washed_blur_fail": ("washed_out",),
        "blue_blob_fail": ("samey_blue",),
    }
    variants: list[SweepVariant] = []
    for label, overrides in cases:
        name = f"{prefix}_{label}" if prefix else label
        variants.append(
            SweepVariant(
                name=name,
                label=label,
                settings=_variant_settings(overrides),
                note="fake caustic water scout: roughness, scale, light size, contrast, tint",
                role=roles.get(label, "candidate"),
                tags=("caustic_water", "fake_caustics", *tags_by_label.get(label, ())),
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


def _curve(name: str, points: list[tuple[float, float, float]], radius: float, mat: Any) -> Any:
    import bpy

    curve = bpy.data.curves.new(name, type="CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 3
    curve.bevel_depth = max(0.001, radius)
    curve.bevel_resolution = 3
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for point, co in zip(spline.points, points, strict=True):
        point.co = (co[0], co[1], co[2], 1.0)
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    obj.data.materials.append(mat)
    return obj


def _configure_world() -> None:
    import bpy

    world = bpy.context.scene.world or bpy.data.worlds.new("caustic water world")
    bpy.context.scene.world = world
    world.color = (0.008, 0.010, 0.014)


def _water_color(settings: CausticWaterSettings) -> tuple[float, float, float, float]:
    return _mix((0.82, 0.92, 1.0, 1.0), (0.14, 0.58, 1.0, 1.0), settings.tint_strength)


def _add_receivers(settings: CausticWaterSettings) -> None:
    import bpy

    floor_value = 0.16 + settings.depth_marker_contrast * 0.10
    floor = principled_material("caustic structured floor", (floor_value, floor_value * 1.03, floor_value * 1.08, 1.0), roughness=0.84)
    wall = principled_material("caustic background wall", (0.055, 0.064, 0.082, 1.0), roughness=0.88)
    dark = principled_material("caustic dark grid lines", (0.025, 0.028, 0.034, 1.0), roughness=0.86)
    warm = principled_material("warm depth receiver", (0.62, 0.46, 0.32, 1.0), roughness=0.64)
    cool = principled_material("cool depth receiver", (0.34, 0.54, 0.72, 1.0), roughness=0.54)

    bpy.ops.mesh.primitive_plane_add(size=5.8, location=(0.0, 0.36, 0.0))
    floor_obj = bpy.context.object
    floor_obj.name = "structured caustic receiver floor"
    floor_obj.data.materials.append(floor)

    bpy.ops.mesh.primitive_plane_add(size=5.6, location=(0.0, 2.45, 1.30), rotation=(math.pi / 2, 0.0, 0.0))
    wall_obj = bpy.context.object
    wall_obj.name = "caustic value-step wall"
    wall_obj.scale.z = 0.64
    wall_obj.data.materials.append(wall)

    for index, x in enumerate((-1.8, -1.2, -0.6, 0.0, 0.6, 1.2, 1.8)):
        _cube(f"floor caustic grid x {index}", (x, 0.38, 0.012), (0.016, 2.55, 0.010), dark)
    for index, y in enumerate((-0.86, -0.36, 0.14, 0.64, 1.14, 1.64)):
        width = 3.8 - index * 0.26
        _cube(f"floor caustic grid y {index}", (0.0, y, 0.014), (width, 0.014, 0.010), dark)

    for index, x in enumerate((-1.8, -1.2, -0.6, 0.0, 0.6, 1.2, 1.8)):
        value = 0.12 + index * 0.07 * settings.depth_marker_contrast
        mat = principled_material(f"background caustic value step {index}", (value, value * 1.04, value * 1.14, 1.0), roughness=0.82)
        _cube(f"background caustic value step {index}", (x, 2.26, 0.72), (0.17, 0.035, 0.55), mat)

    _cube("matte block under water", (-0.62, 0.45, 0.20), (0.36, 0.28, 0.20), warm, rotation=(0.0, 0.0, math.radians(-8.0)))
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=0.24, location=(0.70, 0.26, 0.26))
    bead = bpy.context.object
    bead.name = "curved caustic read bead"
    bead.scale = (1.0, 0.78, 0.82)
    bead.data.materials.append(cool)
    try:
        bpy.ops.object.shade_smooth()
    except RuntimeError:
        pass


def _add_water_sheet(settings: CausticWaterSettings) -> None:
    import bpy

    water = principled_material(
        "transparent water test sheet",
        _water_color(settings),
        roughness=_clamp(settings.water_roughness, 0.0, 1.0),
        alpha=_clamp01(settings.water_alpha),
        transmission_weight=_clamp01(settings.transmission_weight),
        ior=1.333,
    )
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0.0, 0.34, 0.42))
    sheet = bpy.context.object
    sheet.name = "transparent water caustic sheet"
    sheet.scale = (2.15, 1.45, 0.025)
    sheet.data.materials.append(water)


def _add_fake_caustics(settings: CausticWaterSettings) -> None:
    color = _mix((0.88, 0.96, 1.0, 1.0), (0.36, 0.82, 1.0, 1.0), settings.tint_strength * 0.72)
    alpha = min(0.72, 0.10 + settings.caustic_contrast * 0.44)
    mat = transparent_emission_material("fake projected caustic ribbons", color, settings.caustic_strength, alpha)
    count = max(4, min(28, round(4 + settings.caustic_scale * 0.72)))
    frequency = max(0.4, settings.caustic_scale * 0.34)
    amplitude = 0.06 + settings.caustic_contrast * 0.10
    softness = max(0.25, settings.light_size)
    radius = 0.003 + (0.012 / softness) + settings.caustic_contrast * 0.004
    for index in range(count):
        y_base = -0.82 + index * (2.25 / max(1, count - 1))
        points: list[tuple[float, float, float]] = []
        for step in range(9):
            t = step / 8
            x = -1.9 + t * 3.8
            wave = math.sin(t * frequency * math.pi + index * 0.77 + settings.pattern_phase) * amplitude
            wave += math.sin(t * frequency * 0.52 * math.pi + index * 1.91) * amplitude * 0.45
            points.append((x, y_base + wave, 0.035 + index * 0.0008))
        _curve(f"fake floor caustic ribbon {index:02d}", points, radius, mat)

    wall_mat = transparent_emission_material("fake wall caustic echo", color, settings.caustic_strength * 0.42, alpha * 0.58)
    for index in range(max(3, min(10, count // 2))):
        z = 0.58 + index * 0.12
        points = [(-1.75, 2.23, z), (-0.65, 2.22, z + math.sin(index) * 0.05), (0.75, 2.22, z + math.cos(index * 0.7) * 0.05), (1.75, 2.23, z)]
        _curve(f"fake wall caustic echo {index:02d}", points, radius * 0.75, wall_mat)


def _add_lights(settings: CausticWaterSettings) -> None:
    import bpy

    bpy.ops.object.light_add(type="AREA", location=(-1.45, -1.55 - settings.light_distance * 0.24, 2.35 + settings.light_distance * 0.25))
    light = bpy.context.object
    light.name = "controllable caustic source light"
    light.data.energy = 340 + settings.caustic_strength * 180
    light.data.size = max(0.02, settings.light_size)
    light.data.color = _water_color(settings)[:3]
    look_at(light, (0.0, 0.38, 0.12))

    glow = emission_material("visible caustic source marker", _water_color(settings), 0.34)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=0.055 + settings.light_size * 0.018, location=light.location)
    marker = bpy.context.object
    marker.name = "visible source size marker"
    marker.data.materials.append(glow)


def _add_camera() -> None:
    add_orbit_camera(
        name=CAUSTIC_WATER_CAMERA,
        target=(0.0, 0.54, 0.52),
        distance=4.8,
        lens_mm=58.0,
        yaw_degrees=-3.0,
        pitch_degrees=10.0,
    )


def build_caustic_water_scene(settings: CausticWaterSettings | Mapping[str, Any] | None = None) -> None:
    caustic_settings = coerce_caustic_water_settings(settings)
    clear_scene()
    _configure_world()
    _add_receivers(caustic_settings)
    _add_water_sheet(caustic_settings)
    _add_fake_caustics(caustic_settings)
    _add_lights(caustic_settings)
    _add_camera()
