from __future__ import annotations

import dataclasses
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from blender_workbench.camera import add_orbit_camera, look_at
from blender_workbench.materials import emission_material, principled_material
from blender_workbench.primitives import add_soft_horizon_band
from blender_workbench.sweep import SweepVariant


SMOKE_BILLBOARD_CAMERA = "smoke_billboard_camera"
SMOKE_BILLBOARD_MODES = ("staggered_stack", "camera_facing", "fixed_plane")


@dataclass(frozen=True)
class SmokeBillboardSettings:
    alpha: float = 0.105
    strength: float = 0.38
    edge_feather: float = 0.62
    noise_scale: float = 9.0
    noise_magnitude: float = 0.20
    anisotropy: float = 0.36
    layer_count: int = 5
    layer_spacing: float = 0.18
    parallax: float = 0.16
    billboard_mode: str = "staggered_stack"
    backlight_strength: float = 480.0
    backlight_warmth: float = 0.48
    card_width: float = 3.7
    card_height: float = 1.9
    haze_lift: float = 0.08
    smoke_color: tuple[float, float, float, float] = (0.56, 0.62, 0.68, 1.0)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _clamp01(value: float) -> float:
    return _clamp(value, 0.0, 1.0)


def _normalized_mode(value: str) -> str:
    if value in SMOKE_BILLBOARD_MODES:
        return value
    return "staggered_stack"


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


def coerce_smoke_billboard_settings(settings: SmokeBillboardSettings | Mapping[str, Any] | None = None) -> SmokeBillboardSettings:
    if isinstance(settings, SmokeBillboardSettings):
        return settings
    data = dataclasses.asdict(SmokeBillboardSettings())
    if settings:
        data.update({key: value for key, value in dict(settings).items() if key in data})
    data["billboard_mode"] = _normalized_mode(str(data["billboard_mode"]))
    return SmokeBillboardSettings(**data)


def smoke_billboard_descriptor(settings: SmokeBillboardSettings | Mapping[str, Any] | None = None) -> dict[str, Any]:
    smoke = coerce_smoke_billboard_settings(settings)
    layer_count = max(1, int(smoke.layer_count))
    edge_feather = _clamp01(smoke.edge_feather)
    return {
        "technique": "transparent_alpha_billboards",
        "volume_simulation": False,
        "billboard_mode": _normalized_mode(smoke.billboard_mode),
        "layer_count": layer_count,
        "per_layer_alpha": _clamp01(smoke.alpha),
        "edge_feather": edge_feather,
        "feather_steps": max(0, int(round(edge_feather * 8))),
        "noise_scale": max(0.1, float(smoke.noise_scale)),
        "noise_magnitude": _clamp(smoke.noise_magnitude, 0.0, 0.75),
        "fake_forward_scatter": _clamp01(smoke.anisotropy),
        "layer_spacing": max(0.02, float(smoke.layer_spacing)),
        "parallax": max(0.0, float(smoke.parallax)),
        "diagnostics": ("foreground_markers", "midground_subject", "background_value_steps", "back_rim_light"),
    }


def _variant_settings(overrides: Mapping[str, Any]) -> dict[str, Any]:
    data = dataclasses.asdict(SmokeBillboardSettings())
    data.update(dict(overrides))
    smoke = coerce_smoke_billboard_settings(data)
    payload = dataclasses.asdict(smoke)
    payload["billboard_stack"] = smoke_billboard_descriptor(smoke)
    return payload


def smoke_billboard_variants(*, prefix: str = "smoke") -> list[SweepVariant]:
    cases: tuple[tuple[str, Mapping[str, Any]], ...] = (
        ("thin_haze", {"alpha": 0.065, "strength": 0.34, "layer_count": 4, "edge_feather": 0.76}),
        ("soft_mist", {}),
        ("dense_depth", {"alpha": 0.15, "strength": 0.42, "layer_count": 7, "layer_spacing": 0.14, "parallax": 0.18}),
        ("warm_backscatter", {"backlight_warmth": 0.86, "anisotropy": 0.66, "backlight_strength": 620.0}),
        ("cool_backscatter", {"backlight_warmth": 0.10, "anisotropy": 0.58, "backlight_strength": 560.0}),
        ("wide_parallax", {"layer_count": 6, "layer_spacing": 0.25, "parallax": 0.36, "edge_feather": 0.68}),
        ("camera_facing_soft", {"billboard_mode": "camera_facing", "edge_feather": 0.82, "alpha": 0.095, "noise_magnitude": 0.12}),
        ("fixed_plane_graphic", {"billboard_mode": "fixed_plane", "edge_feather": 0.34, "alpha": 0.12, "noise_magnitude": 0.10}),
        ("invisible_haze_fail", {"alpha": 0.018, "strength": 0.10, "layer_count": 3, "noise_magnitude": 0.02}),
        ("dirty_card_fail", {"alpha": 0.22, "strength": 0.46, "edge_feather": 0.18, "noise_scale": 26.0, "noise_magnitude": 0.72}),
        ("opaque_wall_fail", {"alpha": 0.55, "strength": 0.64, "edge_feather": 0.06, "layer_count": 3, "layer_spacing": 0.04}),
    )
    roles = {
        "thin_haze": "baseline",
        "invisible_haze_fail": "failure_anchor",
        "dirty_card_fail": "failure_anchor",
        "opaque_wall_fail": "failure_anchor",
    }
    tags_by_label = {
        "invisible_haze_fail": ("too_subtle",),
        "dirty_card_fail": ("dirty_card", "noisy_alpha"),
        "opaque_wall_fail": ("opaque_wall", "too_far"),
    }
    variants: list[SweepVariant] = []
    for label, overrides in cases:
        name = f"{prefix}_{label}" if prefix else label
        variants.append(
            SweepVariant(
                name=name,
                label=label,
                settings=_variant_settings(overrides),
                note="general scene smoke and alpha-billboard card stack",
                role=roles.get(label, "candidate"),
                tags=("smoke_billboard", "alpha_billboard", *tags_by_label.get(label, ())),
            )
        )
    return variants


def clear_scene() -> None:
    import bpy

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def _shade_smooth() -> None:
    import bpy

    try:
        bpy.ops.object.shade_smooth()
    except RuntimeError:
        pass


def _cube(name: str, location, scale, mat, rotation=(0.0, 0.0, 0.0)) -> Any:
    import bpy

    bpy.ops.mesh.primitive_cube_add(size=1, location=location, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(mat)
    return obj


def _plane(name: str, location, scale, mat, rotation=(math.pi / 2, 0.0, 0.0)) -> Any:
    import bpy

    bpy.ops.mesh.primitive_plane_add(size=1, location=location, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(mat)
    return obj


def _configure_world() -> None:
    import bpy

    world = bpy.context.scene.world or bpy.data.worlds.new("smoke billboard world")
    bpy.context.scene.world = world
    world.color = (0.006, 0.007, 0.010)


def _add_stage(settings: SmokeBillboardSettings) -> None:
    import bpy

    floor_mat = principled_material("smoke matte floor", (0.050, 0.048, 0.052, 1.0), roughness=0.92)
    wall_mat = principled_material("smoke diagnostic wall", (0.032, 0.038, 0.050, 1.0), roughness=0.88)
    subject_mat = principled_material("midground subject matte clay", (0.34, 0.29, 0.24, 1.0), roughness=0.78)
    marker_mat = principled_material("foreground marker dark", (0.024, 0.025, 0.028, 1.0), roughness=0.82)
    tick_mat = emission_material("foreground tick glints", (0.74, 0.86, 1.0, 1.0), 0.22)

    bpy.ops.mesh.primitive_plane_add(size=7.0, location=(0.0, 0.75, 0.0))
    floor = bpy.context.object
    floor.name = "matte floor showing smoke wash"
    floor.data.materials.append(floor_mat)

    _plane("background wall behind alpha smoke", (0.0, 2.86, 1.06), (5.6, 1.75, 1.0), wall_mat)

    for index, x in enumerate((-2.1, -1.4, -0.7, 0.0, 0.7, 1.4, 2.1)):
        value = 0.07 + index * 0.055
        mat = principled_material(f"background value step {index}", (value, value * 1.06, value * 1.18, 1.0), roughness=0.84)
        _plane(f"background value step {index}", (x, 2.84, 1.05), (0.34, 1.42, 1.0), mat)

    for index, x in enumerate((-2.45, -1.75, -1.05, -0.35, 0.35, 1.05, 1.75, 2.45)):
        _cube(f"thin background stripe {index}", (x, 2.78, 1.09), (0.018, 0.024, 0.74), marker_mat)

    for index, x in enumerate((-1.85, -1.15, 1.15, 1.85)):
        _cube(f"foreground marker post {index}", (x, -0.32, 0.46), (0.035, 0.035, 0.46), marker_mat)
        _cube(f"foreground marker tick {index}", (x, -0.34, 0.92), (0.11, 0.026, 0.020), tick_mat)

    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=0.28, depth=0.95, location=(0.0, 1.38, 0.50))
    body = bpy.context.object
    body.name = "midground subject torso exposing smoke depth"
    body.data.materials.append(subject_mat)
    _shade_smooth()

    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=0.22, location=(0.0, 1.38, 1.08))
    head = bpy.context.object
    head.name = "midground subject head silhouette"
    head.scale = (0.86, 0.72, 1.05)
    head.data.materials.append(subject_mat)
    _shade_smooth()

    glow_color = _mix((0.45, 0.58, 1.0, 1.0), (1.0, 0.62, 0.28, 1.0), settings.backlight_warmth)
    add_soft_horizon_band(
        name="low forward-scatter diagnostic glow",
        location=(0.0, 2.66, 1.04),
        width=4.5,
        height=0.42 + settings.anisotropy * 0.28,
        color=glow_color,
        strength=0.24 + settings.anisotropy * 0.22,
        alpha=0.18 + settings.anisotropy * 0.16,
        feather_steps=6,
        center_fraction=0.34,
        noise_strength=0.0,
        noise_scale=5.0,
    )


def _add_smoke_layers(settings: SmokeBillboardSettings) -> None:
    layer_count = max(1, min(12, int(settings.layer_count)))
    spacing = max(0.02, float(settings.layer_spacing))
    edge_feather = _clamp01(settings.edge_feather)
    feather_steps = max(0, int(round(edge_feather * 8)))
    center_fraction = _clamp(0.90 - edge_feather * 0.58, 0.12, 0.92)
    mode = _normalized_mode(settings.billboard_mode)
    cool = settings.smoke_color
    warm = (
        min(1.0, settings.smoke_color[0] + 0.22),
        min(1.0, settings.smoke_color[1] + 0.09),
        max(0.0, settings.smoke_color[2] - 0.12),
        1.0,
    )

    mid = (layer_count - 1) * 0.5
    for index in range(layer_count):
        frac = 0.0 if layer_count == 1 else index / (layer_count - 1)
        phase = index * 1.618
        y = 0.78 + (index - mid) * spacing
        x = math.sin(phase) * max(0.0, settings.parallax)
        z = 0.78 + settings.haze_lift + math.cos(index * 0.91) * settings.parallax * 0.12
        width = settings.card_width * (0.92 + 0.06 * index)
        height = settings.card_height * (0.90 + 0.12 * math.sin(index * 0.73) ** 2)
        layer_alpha = _clamp01(settings.alpha) * (0.84 + 0.20 * frac)
        layer_strength = settings.strength * (0.80 + settings.anisotropy * (0.30 + 0.34 * frac))
        layer_color = _mix(cool, warm, settings.backlight_warmth * (0.72 + 0.22 * frac))
        bands = add_soft_horizon_band(
            name=f"smoke alpha billboard layer {index:02d}",
            location=(x, y, z),
            width=width,
            height=height,
            color=layer_color,
            strength=layer_strength,
            alpha=layer_alpha,
            feather_steps=feather_steps,
            center_fraction=center_fraction,
            noise_strength=settings.noise_magnitude,
            noise_scale=settings.noise_scale,
        )
        band = bands[0]
        if mode == "camera_facing":
            angle = 0.0
        elif mode == "fixed_plane":
            angle = math.radians(4.0)
        else:
            angle = (index - mid) * 0.035 + math.sin(index * 2.1) * 0.025
        band.rotation_euler = (math.pi / 2, 0.0, angle)
        if hasattr(band, "visible_shadow"):
            band.visible_shadow = False


def _add_lights(settings: SmokeBillboardSettings) -> None:
    import bpy

    color = _mix((0.42, 0.52, 1.0, 1.0), (1.0, 0.60, 0.27, 1.0), settings.backlight_warmth)
    bpy.ops.object.light_add(type="AREA", location=(0.0, 2.55, 1.78))
    back = bpy.context.object
    back.name = "smoke back rim light"
    back.data.energy = settings.backlight_strength
    back.data.size = 3.8
    back.data.color = color[:3]
    look_at(back, (0.0, 0.48, 0.82))

    bpy.ops.object.light_add(type="AREA", location=(-2.8, -1.65, 2.35))
    key = bpy.context.object
    key.name = "weak foreground shape key"
    key.data.energy = 95
    key.data.size = 4.4
    key.data.color = (0.72, 0.78, 0.86)
    look_at(key, (0.0, 1.1, 0.65))


def _add_camera() -> None:
    add_orbit_camera(
        name=SMOKE_BILLBOARD_CAMERA,
        target=(0.0, 1.18, 0.82),
        distance=5.3,
        lens_mm=54.0,
        yaw_degrees=0.0,
        pitch_degrees=5.2,
    )


def build_smoke_billboard_scene(settings: SmokeBillboardSettings | Mapping[str, Any] | None = None) -> None:
    smoke_settings = coerce_smoke_billboard_settings(settings)
    clear_scene()
    _configure_world()
    _add_stage(smoke_settings)
    _add_smoke_layers(smoke_settings)
    _add_lights(smoke_settings)
    _add_camera()
