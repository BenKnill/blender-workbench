from __future__ import annotations

import dataclasses
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from blender_workbench.camera import add_orbit_camera, look_at
from blender_workbench.materials import emission_material, principled_material, set_node_input
from blender_workbench.sweep import SweepVariant


LAYERED_MATERIAL_CAMERA = "layered_material_camera"


@dataclass(frozen=True)
class LayeredMaterialSettings:
    component: str = "balanced_skin"
    diffuse_weight: float = 0.58
    epidermal_sss_weight: float = 0.26
    dermal_sss_weight: float = 0.22
    backscatter_weight: float = 0.18
    soft_specular_weight: float = 0.34
    wet_specular_weight: float = 0.07
    bump_weight: float = 0.16
    bump_scale: float = 42.0
    base_color: tuple[float, float, float, float] = (0.88, 0.58, 0.48, 1.0)
    backlight_energy: float = 360.0
    key_light_energy: float = 320.0
    specular_light_energy: float = 190.0
    subject_scale: tuple[float, float, float] = (0.72, 0.66, 0.78)


def coerce_layered_material_settings(
    settings: LayeredMaterialSettings | Mapping[str, Any] | None = None,
) -> LayeredMaterialSettings:
    if isinstance(settings, LayeredMaterialSettings):
        return settings
    data = dataclasses.asdict(LayeredMaterialSettings())
    if settings:
        data.update({key: value for key, value in dict(settings).items() if key in data})
    return LayeredMaterialSettings(**data)


def _weight_summary(settings: LayeredMaterialSettings | Mapping[str, Any] | None = None) -> dict[str, float]:
    values = coerce_layered_material_settings(settings)
    return {
        "diffuse": values.diffuse_weight,
        "epidermal_sss": values.epidermal_sss_weight,
        "dermal_sss": values.dermal_sss_weight,
        "backscatter": values.backscatter_weight,
        "soft_specular": values.soft_specular_weight,
        "wet_specular": values.wet_specular_weight,
        "bump": values.bump_weight,
    }


def layered_material_weight_summary(settings: LayeredMaterialSettings | Mapping[str, Any] | None = None) -> dict[str, float]:
    """Return the explicit layer weights that should be preserved in metadata."""
    return _weight_summary(settings)


def layered_material_variants(*, prefix: str = "layer") -> list[SweepVariant]:
    base = dataclasses.asdict(LayeredMaterialSettings())
    cases: tuple[tuple[str, dict[str, Any], str, tuple[str, ...]], ...] = (
        (
            "diffuse_only",
            {
                "component": "base_unscattered_diffuse",
                "diffuse_weight": 1.0,
                "epidermal_sss_weight": 0.0,
                "dermal_sss_weight": 0.0,
                "backscatter_weight": 0.0,
                "soft_specular_weight": 0.0,
                "wet_specular_weight": 0.0,
                "bump_weight": 0.0,
                "backlight_energy": 180.0,
            },
            "baseline",
            ("component", "diffuse"),
        ),
        (
            "epidermal_sss",
            {
                "component": "shallow_epidermal_sss",
                "diffuse_weight": 0.42,
                "epidermal_sss_weight": 0.82,
                "dermal_sss_weight": 0.08,
                "backscatter_weight": 0.08,
                "soft_specular_weight": 0.08,
                "wet_specular_weight": 0.0,
                "bump_weight": 0.02,
            },
            "candidate",
            ("component", "sss"),
        ),
        (
            "dermal_backscatter",
            {
                "component": "deep_dermal_backscatter",
                "diffuse_weight": 0.34,
                "epidermal_sss_weight": 0.18,
                "dermal_sss_weight": 0.86,
                "backscatter_weight": 0.78,
                "soft_specular_weight": 0.05,
                "wet_specular_weight": 0.0,
                "bump_weight": 0.0,
                "backlight_energy": 640.0,
            },
            "candidate",
            ("component", "backscatter"),
        ),
        (
            "soft_specular",
            {
                "component": "broad_soft_specular",
                "diffuse_weight": 0.70,
                "epidermal_sss_weight": 0.12,
                "dermal_sss_weight": 0.06,
                "backscatter_weight": 0.02,
                "soft_specular_weight": 0.92,
                "wet_specular_weight": 0.0,
                "bump_weight": 0.04,
                "specular_light_energy": 260.0,
            },
            "candidate",
            ("component", "specular"),
        ),
        (
            "wet_highlight",
            {
                "component": "tight_wet_specular",
                "diffuse_weight": 0.62,
                "epidermal_sss_weight": 0.10,
                "dermal_sss_weight": 0.04,
                "backscatter_weight": 0.02,
                "soft_specular_weight": 0.20,
                "wet_specular_weight": 0.86,
                "bump_weight": 0.05,
                "specular_light_energy": 360.0,
            },
            "candidate",
            ("component", "wet_specular"),
        ),
        (
            "bump_roughness",
            {
                "component": "bump_roughness_detail",
                "diffuse_weight": 0.72,
                "epidermal_sss_weight": 0.12,
                "dermal_sss_weight": 0.08,
                "backscatter_weight": 0.03,
                "soft_specular_weight": 0.24,
                "wet_specular_weight": 0.0,
                "bump_weight": 0.68,
                "bump_scale": 78.0,
            },
            "candidate",
            ("component", "bump"),
        ),
        (
            "balanced_skin",
            dataclasses.asdict(LayeredMaterialSettings()),
            "candidate",
            ("combined", "preset_candidate"),
        ),
        (
            "plastic_fail",
            {
                "component": "plastic_single_layer_fail",
                "diffuse_weight": 0.96,
                "epidermal_sss_weight": 0.0,
                "dermal_sss_weight": 0.0,
                "backscatter_weight": 0.0,
                "soft_specular_weight": 0.66,
                "wet_specular_weight": 0.58,
                "bump_weight": 0.0,
                "base_color": (0.86, 0.50, 0.43, 1.0),
                "backlight_energy": 120.0,
            },
            "failure_anchor",
            ("failure_anchor", "plastic"),
        ),
        (
            "waxy_blur_fail",
            {
                "component": "waxy_sss_blur_fail",
                "diffuse_weight": 0.16,
                "epidermal_sss_weight": 0.92,
                "dermal_sss_weight": 0.84,
                "backscatter_weight": 0.46,
                "soft_specular_weight": 0.02,
                "wet_specular_weight": 0.0,
                "bump_weight": 0.0,
                "backlight_energy": 760.0,
            },
            "failure_anchor",
            ("failure_anchor", "waxy"),
        ),
        (
            "over_combined_fail",
            {
                "component": "all_layers_maxed_fail",
                "diffuse_weight": 0.98,
                "epidermal_sss_weight": 0.92,
                "dermal_sss_weight": 0.92,
                "backscatter_weight": 0.95,
                "soft_specular_weight": 0.92,
                "wet_specular_weight": 0.88,
                "bump_weight": 0.80,
                "bump_scale": 96.0,
                "backlight_energy": 900.0,
                "specular_light_energy": 420.0,
            },
            "failure_anchor",
            ("failure_anchor", "overdone"),
        ),
    )

    variants: list[SweepVariant] = []
    for label, overrides, role, tags in cases:
        data = dict(base)
        data.update(overrides)
        data["layer_weights"] = _weight_summary(data)
        variants.append(
            SweepVariant(
                name=f"{prefix}_{label}" if prefix else label,
                label=label,
                settings=data,
                note="layered material component scout for diffuse, SSS, specular, and bump contributions",
                role=role,
                tags=("layered_material", "sss_components", *tags),
            )
        )
    return variants


def clear_scene() -> None:
    import bpy

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _mix_rgb(settings: LayeredMaterialSettings) -> tuple[float, float, float, float]:
    diffuse = _clamp01(settings.diffuse_weight)
    epidermal = _clamp01(settings.epidermal_sss_weight)
    dermal = _clamp01(settings.dermal_sss_weight)
    backscatter = _clamp01(settings.backscatter_weight)
    total = max(0.001, diffuse + epidermal + dermal + backscatter)
    colors = (
        (settings.base_color, diffuse),
        ((1.0, 0.66, 0.52, 1.0), epidermal),
        ((0.92, 0.36, 0.28, 1.0), dermal),
        ((1.0, 0.18, 0.10, 1.0), backscatter * 0.82),
    )
    return (
        _clamp01(sum(color[0] * weight for color, weight in colors) / total),
        _clamp01(sum(color[1] * weight for color, weight in colors) / total),
        _clamp01(sum(color[2] * weight for color, weight in colors) / total),
        1.0,
    )


def _subsurface_radius(settings: LayeredMaterialSettings) -> tuple[float, float, float]:
    dermal = _clamp01(settings.dermal_sss_weight)
    backscatter = _clamp01(settings.backscatter_weight)
    epidermal = _clamp01(settings.epidermal_sss_weight)
    return (
        _clamp(0.72 + dermal * 0.22 + backscatter * 0.18, 0.08, 1.0),
        _clamp(0.42 + epidermal * 0.14 - backscatter * 0.16, 0.08, 0.82),
        _clamp(0.20 + epidermal * 0.10 - dermal * 0.10 - backscatter * 0.08, 0.04, 0.52),
    )


def _apply_principled_overrides(mat: Any, settings: LayeredMaterialSettings) -> None:
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if not bsdf:
        return
    specular = _clamp(0.16 + settings.soft_specular_weight * 0.62 + settings.wet_specular_weight * 0.36, 0.0, 1.0)
    coat = _clamp01(settings.wet_specular_weight)
    set_node_input(bsdf, ["Specular IOR Level", "Specular"], specular)
    set_node_input(bsdf, ["Coat Weight", "Clearcoat"], coat)
    set_node_input(bsdf, ["Coat Roughness", "Clearcoat Roughness"], _clamp(0.08 - coat * 0.055, 0.018, 0.12))
    set_node_input(bsdf, ["Sheen Weight", "Sheen"], _clamp01(settings.soft_specular_weight * 0.22))


def _apply_noise_bump(mat: Any, settings: LayeredMaterialSettings) -> None:
    strength = _clamp01(settings.bump_weight)
    if strength <= 0:
        return
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    if not bsdf or "Normal" not in bsdf.inputs:
        return
    noise = nodes.new(type="ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = settings.bump_scale
    noise.inputs["Detail"].default_value = 12.0
    noise.inputs["Roughness"].default_value = 0.62
    bump = nodes.new(type="ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.02 + strength * 0.18
    bump.inputs["Distance"].default_value = 0.045
    links.new(noise.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])


def _material(settings: LayeredMaterialSettings) -> Any:
    sss_weight = _clamp01(
        settings.epidermal_sss_weight * 0.22 + settings.dermal_sss_weight * 0.36 + settings.backscatter_weight * 0.40
    )
    subsurface_scale = 0.18 + settings.epidermal_sss_weight * 0.26 + settings.dermal_sss_weight * 0.52 + settings.backscatter_weight * 0.72
    roughness = _clamp(0.78 - settings.soft_specular_weight * 0.28 - settings.wet_specular_weight * 0.58 + settings.bump_weight * 0.10, 0.10, 0.92)
    mat = principled_material(
        "layered material study",
        _mix_rgb(settings),
        roughness=roughness,
        subsurface_weight=sss_weight,
        subsurface_radius=_subsurface_radius(settings),
        subsurface_scale=subsurface_scale if sss_weight > 0 else 0.0,
    )
    _apply_principled_overrides(mat, settings)
    _apply_noise_bump(mat, settings)
    return mat


def _cube(name: str, location, scale, mat: Any) -> Any:
    import bpy

    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(mat)
    return obj


def _shade_smooth(obj: Any) -> None:
    import bpy

    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.shade_smooth()
    obj.select_set(False)


def _add_set(settings: LayeredMaterialSettings) -> None:
    import bpy

    floor_mat = principled_material("layered floor", (0.22, 0.21, 0.22, 1.0), roughness=0.88)
    wall_mat = principled_material("layered matte wall", (0.12, 0.13, 0.16, 1.0), roughness=0.92)
    dark_mat = principled_material("layered dark stripe", (0.035, 0.038, 0.044, 1.0), roughness=0.86)
    cool_mat = principled_material("cool structured cards", (0.24, 0.44, 0.76, 1.0), roughness=0.62)
    warm_mat = principled_material("warm structured cards", (0.92, 0.48, 0.24, 1.0), roughness=0.58)
    gloss_mat = principled_material("white specular catch card", (0.92, 0.90, 0.84, 1.0), roughness=0.22)

    bpy.ops.mesh.primitive_plane_add(size=4.8, location=(0, 0.18, 0))
    floor = bpy.context.object
    floor.name = "layered material floor"
    floor.data.materials.append(floor_mat)

    bpy.ops.mesh.primitive_plane_add(size=4.8, location=(0, 1.82, 1.72), rotation=(math.pi / 2, 0, 0))
    wall = bpy.context.object
    wall.name = "layered material structured wall"
    wall.data.materials.append(wall_mat)

    for index, x in enumerate((-1.42, -0.72, 0.0, 0.72, 1.42)):
        mat = dark_mat if index % 2 == 0 else cool_mat
        _cube(f"floor material scale stripe {index}", (x, 0.28, 0.018), (0.026, 1.72, 0.014), mat)
    for index, x in enumerate((-1.55, -0.92, 0.98, 1.52)):
        mat = warm_mat if index % 2 else cool_mat
        _cube(f"background hue card {index}", (x, 1.79, 0.62 + index * 0.18), (0.10, 0.022, 0.46), mat)
    _cube("narrow white specular reflection card", (-1.24, 1.76, 1.75), (0.07, 0.018, 0.64), gloss_mat)

    rim_mat = emission_material(
        "backscatter warm rim card",
        (1.0, 0.32 + settings.backscatter_weight * 0.18, 0.12, 1.0),
        0.55 + settings.backscatter_weight * 1.15,
    )
    _cube("warm backscatter read card", (1.12, 1.69, 1.28), (0.16, 0.018, 0.52), rim_mat)


def _add_subject(settings: LayeredMaterialSettings) -> None:
    import bpy

    mat = _material(settings)

    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=0.72, location=(0.02, 0.26, 0.84))
    dome = bpy.context.object
    dome.name = "layered material main dome"
    dome.scale = settings.subject_scale
    dome.data.materials.append(mat)
    _shade_smooth(dome)

    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=0.27, location=(-0.74, 0.20, 0.54))
    thin = bpy.context.object
    thin.name = "thin backscatter ear"
    thin.scale = (0.44, 0.18, 0.72)
    thin.data.materials.append(mat)
    _shade_smooth(thin)

    bpy.ops.mesh.primitive_cube_add(size=1, location=(0.78, 0.18, 0.52), rotation=(0.0, 0.0, math.radians(-11.0)))
    cheek = bpy.context.object
    cheek.name = "angled specular and bump cheek"
    cheek.scale = (0.18, 0.38, 0.40)
    cheek.data.materials.append(mat)
    bevel = cheek.modifiers.new("soft cheek bevel", "BEVEL")
    bevel.width = 0.12
    bevel.segments = 10
    cheek.modifiers.new("weighted normal", "WEIGHTED_NORMAL")


def _add_lights(settings: LayeredMaterialSettings) -> None:
    import bpy

    bpy.ops.object.light_add(type="AREA", location=(-1.8, -2.0, 2.25))
    key = bpy.context.object
    key.name = "layered material broad key"
    key.data.energy = settings.key_light_energy
    key.data.size = 3.2
    key.data.color = (1.0, 0.78, 0.62)
    look_at(key, (0.0, 0.24, 0.82))

    bpy.ops.object.light_add(type="AREA", location=(-1.18, -0.84, 1.38))
    spec = bpy.context.object
    spec.name = "layered material grazing specular"
    spec.data.energy = settings.specular_light_energy * (0.68 + settings.soft_specular_weight * 0.42 + settings.wet_specular_weight * 0.52)
    spec.data.size = _clamp(1.6 - settings.wet_specular_weight * 1.1, 0.26, 1.8)
    spec.data.color = (0.92, 0.96, 1.0)
    look_at(spec, (0.24, 0.22, 0.75))

    bpy.ops.object.light_add(type="AREA", location=(0.55, 1.38, 1.08))
    back = bpy.context.object
    back.name = "layered material warm backscatter"
    back.data.energy = settings.backlight_energy * (0.74 + settings.backscatter_weight * 0.86)
    back.data.size = _clamp(1.15 + settings.dermal_sss_weight * 0.35, 0.6, 1.8)
    back.data.color = (1.0, 0.42, 0.20)
    look_at(back, (-0.22, 0.23, 0.75))


def _add_camera() -> None:
    add_orbit_camera(
        name=LAYERED_MATERIAL_CAMERA,
        target=(0.03, 0.25, 0.82),
        distance=3.75,
        lens_mm=58.0,
        yaw_degrees=-4.0,
        pitch_degrees=9.0,
    )


def build_layered_material_scene(settings: LayeredMaterialSettings | Mapping[str, Any] | None = None) -> None:
    import bpy

    material_settings = coerce_layered_material_settings(settings)
    clear_scene()
    world = bpy.context.scene.world or bpy.data.worlds.new("layered material world")
    bpy.context.scene.world = world
    world.color = (0.018, 0.019, 0.024)
    _add_set(material_settings)
    _add_subject(material_settings)
    _add_lights(material_settings)
    _add_camera()
