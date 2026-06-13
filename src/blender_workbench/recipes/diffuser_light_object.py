from __future__ import annotations

import dataclasses
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from blender_workbench.camera import add_orbit_camera, look_at
from blender_workbench.materials import emission_material, principled_material
from blender_workbench.sweep import SweepVariant


DIFFUSER_LIGHT_OBJECT_CAMERA = "diffuser_light_object_camera"
DIFFUSER_SHELL_SHAPES = ("sphere", "cylinder", "faceted", "organic")


@dataclass(frozen=True)
class DiffuserLightObjectSettings:
    shell_shape: str = "sphere"
    shell_opacity: float = 0.42
    transmission_weight: float = 0.22
    subsurface_weight: float = 0.34
    shell_roughness: float = 0.46
    inner_emitter_strength: float = 360.0
    inner_emitter_size: float = 0.42
    pattern_density: int = 6
    pattern_magnitude: float = 0.24
    warmth: float = 0.58
    shadow_softness: float = 0.62
    diffuser_distance: float = 1.0
    diffuser_height: float = 1.55
    shell_size: float = 0.74


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _clamp01(value: float) -> float:
    return _clamp(value, 0.0, 1.0)


def _normalized_shape(value: str) -> str:
    if value in DIFFUSER_SHELL_SHAPES:
        return value
    return "sphere"


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


def coerce_diffuser_light_object_settings(
    settings: DiffuserLightObjectSettings | Mapping[str, Any] | None = None,
) -> DiffuserLightObjectSettings:
    if isinstance(settings, DiffuserLightObjectSettings):
        return settings
    data = dataclasses.asdict(DiffuserLightObjectSettings())
    if settings:
        data.update({key: value for key, value in dict(settings).items() if key in data})
    data["shell_shape"] = _normalized_shape(str(data["shell_shape"]))
    return DiffuserLightObjectSettings(**data)


def diffuser_light_object_descriptor(settings: DiffuserLightObjectSettings | Mapping[str, Any] | None = None) -> dict[str, Any]:
    diffuser = coerce_diffuser_light_object_settings(settings)
    return {
        "technique": "visible_translucent_diffuser_object",
        "shell_shape": _normalized_shape(diffuser.shell_shape),
        "available_shell_shapes": DIFFUSER_SHELL_SHAPES,
        "shell_opacity": _clamp01(diffuser.shell_opacity),
        "transmission_weight": _clamp01(diffuser.transmission_weight),
        "subsurface_weight": _clamp01(diffuser.subsurface_weight),
        "inner_emitter_strength": max(0.0, float(diffuser.inner_emitter_strength)),
        "inner_emitter_size": max(0.05, float(diffuser.inner_emitter_size)),
        "pattern_density": max(0, int(diffuser.pattern_density)),
        "pattern_magnitude": _clamp(diffuser.pattern_magnitude, 0.0, 1.0),
        "shadow_softness": _clamp01(diffuser.shadow_softness),
        "diagnostic_receivers": ("matte_hard_surface_block", "organic_curved_form", "glossy_tinted_object"),
    }


def _variant_settings(overrides: Mapping[str, Any]) -> dict[str, Any]:
    data = dataclasses.asdict(DiffuserLightObjectSettings())
    data.update(dict(overrides))
    diffuser = coerce_diffuser_light_object_settings(data)
    payload = dataclasses.asdict(diffuser)
    payload["diffuser_object"] = diffuser_light_object_descriptor(diffuser)
    return payload


def diffuser_light_object_variants(*, prefix: str = "diffuser") -> list[SweepVariant]:
    cases: tuple[tuple[str, Mapping[str, Any]], ...] = (
        ("china_ball", {"shell_shape": "sphere", "shell_opacity": 0.40, "inner_emitter_strength": 360.0}),
        ("thin_shell", {"shell_shape": "sphere", "shell_opacity": 0.24, "transmission_weight": 0.40, "subsurface_weight": 0.24}),
        ("warm_lantern", {"shell_shape": "cylinder", "warmth": 0.86, "inner_emitter_strength": 420.0, "pattern_density": 5}),
        ("cool_cylinder", {"shell_shape": "cylinder", "warmth": 0.18, "shadow_softness": 0.74, "pattern_density": 4}),
        ("faceted_print", {"shell_shape": "faceted", "pattern_density": 8, "pattern_magnitude": 0.34, "inner_emitter_size": 0.34}),
        ("organic_glow", {"shell_shape": "organic", "subsurface_weight": 0.56, "shell_opacity": 0.48, "pattern_density": 3}),
        ("close_softbox", {"shell_shape": "sphere", "diffuser_distance": 0.58, "shadow_softness": 0.82, "shell_size": 0.86}),
        ("dense_print", {"shell_shape": "sphere", "pattern_density": 12, "pattern_magnitude": 0.48, "inner_emitter_strength": 390.0}),
        ("opaque_prop_fail", {"shell_opacity": 0.92, "transmission_weight": 0.02, "subsurface_weight": 0.04, "inner_emitter_strength": 260.0}),
        ("overbright_ball_fail", {"shell_opacity": 0.34, "inner_emitter_strength": 1250.0, "inner_emitter_size": 0.78, "pattern_magnitude": 0.08}),
        ("overprinted_fail", {"shell_shape": "faceted", "pattern_density": 18, "pattern_magnitude": 0.92, "shell_opacity": 0.56}),
    )
    roles = {
        "china_ball": "baseline",
        "opaque_prop_fail": "failure_anchor",
        "overbright_ball_fail": "failure_anchor",
        "overprinted_fail": "failure_anchor",
    }
    tags_by_label = {
        "opaque_prop_fail": ("opaque_prop",),
        "overbright_ball_fail": ("overbright",),
        "overprinted_fail": ("overprinted", "noisy_texture"),
    }
    variants: list[SweepVariant] = []
    for label, overrides in cases:
        name = f"{prefix}_{label}" if prefix else label
        variants.append(
            SweepVariant(
                name=name,
                label=label,
                settings=_variant_settings(overrides),
                note="visible translucent diffuser light object scout",
                role=roles.get(label, "candidate"),
                tags=("diffuser_light_object", "translucent_light", *tags_by_label.get(label, ())),
            )
        )
    return variants


def clear_scene() -> None:
    import bpy

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def _shade_smooth(obj: Any) -> None:
    import bpy

    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    try:
        bpy.ops.object.shade_smooth()
    except RuntimeError:
        pass
    obj.select_set(False)


def _cube(name: str, location, scale, mat: Any, rotation=(0.0, 0.0, 0.0)) -> Any:
    import bpy

    bpy.ops.mesh.primitive_cube_add(size=1, location=location, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(mat)
    return obj


def _configure_world() -> None:
    import bpy

    world = bpy.context.scene.world or bpy.data.worlds.new("diffuser light object world")
    bpy.context.scene.world = world
    world.color = (0.008, 0.009, 0.012)


def _diffuser_location(settings: DiffuserLightObjectSettings) -> tuple[float, float, float]:
    return (-1.05, -0.32 * _clamp(settings.diffuser_distance, 0.45, 1.75), settings.diffuser_height)


def _shell_color(settings: DiffuserLightObjectSettings) -> tuple[float, float, float, float]:
    return _mix((0.55, 0.68, 1.0, 1.0), (1.0, 0.68, 0.36, 1.0), settings.warmth)


def _shell_material(settings: DiffuserLightObjectSettings) -> Any:
    color = _shell_color(settings)
    return principled_material(
        "translucent printed diffuser shell",
        color,
        roughness=settings.shell_roughness,
        alpha=_clamp01(settings.shell_opacity),
        subsurface_weight=_clamp01(settings.subsurface_weight),
        subsurface_radius=(1.0, 0.72, 0.42),
        subsurface_scale=0.78,
        transmission_weight=_clamp01(settings.transmission_weight),
        emission=color,
        emission_strength=max(0.0, settings.inner_emitter_strength) / 5200.0,
    )


def _add_receivers(settings: DiffuserLightObjectSettings) -> None:
    import bpy

    floor = principled_material("diffuser receiver floor", (0.18, 0.17, 0.18, 1.0), roughness=0.88)
    wall = principled_material("diffuser receiver wall", (0.07, 0.08, 0.10, 1.0), roughness=0.9)
    hard = principled_material("matte hard surface receiver", (0.54, 0.55, 0.58, 1.0), roughness=0.72, metallic=0.05)
    organic = principled_material("organic receiver warm clay", (0.62, 0.43, 0.31, 1.0), roughness=0.58)
    glossy = principled_material("glossy tinted receiver", (0.36, 0.58, 0.82, 1.0), roughness=0.18, metallic=0.0, transmission_weight=0.16)
    dark = principled_material("small shadow diagnostics", (0.024, 0.023, 0.026, 1.0), roughness=0.78)

    bpy.ops.mesh.primitive_plane_add(size=6.0, location=(0.0, 0.38, 0.0))
    floor_obj = bpy.context.object
    floor_obj.name = "diffuser receiver floor"
    floor_obj.data.materials.append(floor)

    bpy.ops.mesh.primitive_plane_add(size=5.8, location=(0.0, 2.25, 1.45), rotation=(math.pi / 2, 0.0, 0.0))
    wall_obj = bpy.context.object
    wall_obj.name = "diffuser receiver wall"
    wall_obj.data.materials.append(wall)

    _cube("matte hard surface block", (0.10, 0.34, 0.36), (0.48, 0.42, 0.36), hard, rotation=(0.0, 0.0, math.radians(-5.0)))
    _cube("thin hard edge shadow probe", (0.68, 0.18, 0.54), (0.045, 0.22, 0.54), dark, rotation=(0.0, 0.0, math.radians(7.0)))

    bpy.ops.mesh.primitive_uv_sphere_add(segments=40, ring_count=20, radius=0.42, location=(-0.48, 0.58, 0.48))
    blob = bpy.context.object
    blob.name = "organic curved receiver"
    blob.scale = (0.92, 0.74, 1.22)
    blob.data.materials.append(organic)
    _shade_smooth(blob)

    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=0.25, location=(0.86, 0.28, 0.30))
    bead = bpy.context.object
    bead.name = "glossy tinted receiver bead"
    bead.scale = (1.0, 0.88, 0.72)
    bead.data.materials.append(glossy)
    _shade_smooth(bead)

    for index, x in enumerate((-1.25, -0.75, -0.25, 0.25, 0.75, 1.25)):
        _cube(f"background softness ruler {index}", (x, 2.10, 0.42 + index * 0.08), (0.035, 0.035, 0.34), dark)


def _add_shell_object(settings: DiffuserLightObjectSettings, mat: Any) -> Any:
    import bpy

    shape = _normalized_shape(settings.shell_shape)
    location = _diffuser_location(settings)
    size = max(0.16, settings.shell_size)
    if shape == "cylinder":
        bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=size * 0.48, depth=size * 1.35, location=location)
        obj = bpy.context.object
        obj.name = "visible translucent cylinder diffuser"
    elif shape == "faceted":
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=size * 0.72, location=location)
        obj = bpy.context.object
        obj.name = "visible faceted printed diffuser"
    else:
        bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=size * 0.62, location=location)
        obj = bpy.context.object
        obj.name = "visible translucent sphere diffuser"
        if shape == "organic":
            obj.name = "visible organic blob diffuser"
            obj.scale = (1.12, 0.84, 0.96)
    obj.data.materials.append(mat)
    _shade_smooth(obj)
    return obj


def _add_printed_pattern(settings: DiffuserLightObjectSettings) -> None:
    import bpy

    count = max(0, min(24, int(settings.pattern_density)))
    if count == 0 or settings.pattern_magnitude <= 0:
        return
    ink_alpha = _clamp(0.12 + settings.pattern_magnitude * 0.55, 0.08, 0.82)
    ink = principled_material("printed diffuser ink", (0.028, 0.030, 0.034, 1.0), roughness=0.72, alpha=ink_alpha)
    location = _diffuser_location(settings)
    radius = max(0.16, settings.shell_size) * 0.49
    height = max(0.16, settings.shell_size) * 0.88
    for index in range(count):
        frac = 0.0 if count == 1 else index / (count - 1)
        z = location[2] - height * 0.46 + frac * height * 0.92
        ring_radius = radius * (0.74 + 0.24 * math.sin(index * 1.7) ** 2)
        bpy.ops.mesh.primitive_torus_add(
            major_radius=ring_radius,
            minor_radius=0.0035 + settings.pattern_magnitude * 0.006,
            major_segments=48,
            minor_segments=6,
            location=(location[0], location[1], z),
            rotation=(0.0, 0.0, math.radians(index * 7.0)),
        )
        ring = bpy.context.object
        ring.name = f"printed diffuser pattern band {index:02d}"
        ring.data.materials.append(ink)


def _add_inner_emitter(settings: DiffuserLightObjectSettings) -> None:
    import bpy

    location = _diffuser_location(settings)
    color = _shell_color(settings)
    emitter = emission_material("hidden inner diffuser emitter", color, max(0.0, settings.inner_emitter_strength) / 48.0)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=max(0.05, settings.inner_emitter_size), location=location)
    core = bpy.context.object
    core.name = "visible inner emitter core"
    core.data.materials.append(emitter)
    _shade_smooth(core)

    bpy.ops.object.light_add(type="POINT", location=location)
    light = bpy.context.object
    light.name = "diffuser internal light"
    light.data.energy = max(0.0, settings.inner_emitter_strength)
    light.data.color = color[:3]
    light.data.shadow_soft_size = max(0.08, settings.inner_emitter_size * (1.0 + settings.shadow_softness * 2.2))


def _add_fill() -> None:
    import bpy

    bpy.ops.object.light_add(type="AREA", location=(2.2, -2.4, 2.6))
    fill = bpy.context.object
    fill.name = "weak receiver fill"
    fill.data.energy = 55
    fill.data.size = 4.8
    fill.data.color = (0.44, 0.52, 0.70)
    look_at(fill, (0.0, 0.4, 0.55))


def _add_camera() -> None:
    add_orbit_camera(
        name=DIFFUSER_LIGHT_OBJECT_CAMERA,
        target=(-0.12, 0.34, 0.82),
        distance=4.9,
        lens_mm=58.0,
        yaw_degrees=-7.0,
        pitch_degrees=8.0,
    )


def build_diffuser_light_object_scene(settings: DiffuserLightObjectSettings | Mapping[str, Any] | None = None) -> None:
    diffuser_settings = coerce_diffuser_light_object_settings(settings)
    clear_scene()
    _configure_world()
    _add_receivers(diffuser_settings)
    shell_mat = _shell_material(diffuser_settings)
    _add_shell_object(diffuser_settings, shell_mat)
    _add_printed_pattern(diffuser_settings)
    _add_inner_emitter(diffuser_settings)
    _add_fill()
    _add_camera()
