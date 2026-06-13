from __future__ import annotations

import dataclasses
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from blender_workbench.camera import add_orbit_camera, look_at
from blender_workbench.materials import principled_material, set_node_input
from blender_workbench.sweep import SweepVariant


METAL_EDGE_LIGHT_CAMERA = "metal_edge_light_camera"


@dataclass(frozen=True)
class MetalEdgeLightSettings:
    roughness: float = 0.28
    metallic: float = 1.0
    specular_weight: float = 0.72
    anisotropy: float = 0.18
    edge_light_strength: float = 540.0
    edge_light_size: float = 0.82
    key_light_strength: float = 260.0
    fill_light_strength: float = 48.0
    environment_brightness: float = 0.025
    bevel_scale: float = 0.075
    scratch_strength: float = 0.06
    scratch_scale: float = 54.0
    tint: tuple[float, float, float, float] = (0.78, 0.74, 0.68, 1.0)
    rim_color: tuple[float, float, float] = (0.78, 0.88, 1.0)


def coerce_metal_edge_light_settings(
    settings: MetalEdgeLightSettings | Mapping[str, Any] | None = None,
) -> MetalEdgeLightSettings:
    if isinstance(settings, MetalEdgeLightSettings):
        return settings
    data = dataclasses.asdict(MetalEdgeLightSettings())
    if settings:
        data.update({key: value for key, value in dict(settings).items() if key in data})
    return MetalEdgeLightSettings(**data)


def _descriptor(settings: MetalEdgeLightSettings | Mapping[str, Any]) -> dict[str, Any]:
    values = coerce_metal_edge_light_settings(settings)
    return {
        "roughness": values.roughness,
        "metallic": values.metallic,
        "specular_weight": values.specular_weight,
        "anisotropy": values.anisotropy,
        "edge_light_strength": values.edge_light_strength,
        "edge_light_size": values.edge_light_size,
        "bevel_scale": values.bevel_scale,
        "scratch_strength": values.scratch_strength,
        "scratch_scale": values.scratch_scale,
        "rim_color": values.rim_color,
    }


def metal_edge_light_variants(*, prefix: str = "metal") -> list[SweepVariant]:
    base = dataclasses.asdict(MetalEdgeLightSettings())
    cases: tuple[tuple[str, Mapping[str, Any], str, tuple[str, ...]], ...] = (
        (
            "mirror_edge",
            {"roughness": 0.045, "edge_light_strength": 620.0, "edge_light_size": 0.48, "scratch_strength": 0.0},
            "candidate",
            ("mirror", "edge_light"),
        ),
        (
            "satin_balanced",
            dataclasses.asdict(MetalEdgeLightSettings()),
            "candidate",
            ("satin", "balanced"),
        ),
        (
            "brushed_cool",
            {
                "roughness": 0.22,
                "anisotropy": 0.62,
                "scratch_strength": 0.12,
                "scratch_scale": 92.0,
                "rim_color": (0.58, 0.74, 1.0),
            },
            "candidate",
            ("brushed", "cool_rim"),
        ),
        (
            "warm_cutline",
            {
                "roughness": 0.18,
                "edge_light_strength": 780.0,
                "edge_light_size": 0.38,
                "rim_color": (1.0, 0.66, 0.38),
                "bevel_scale": 0.052,
            },
            "candidate",
            ("warm_rim", "thin_edge"),
        ),
        (
            "broad_soft_edge",
            {
                "roughness": 0.38,
                "edge_light_strength": 700.0,
                "edge_light_size": 2.1,
                "key_light_strength": 320.0,
                "fill_light_strength": 80.0,
            },
            "candidate",
            ("softbox", "broad_edge"),
        ),
        (
            "dark_silhouette",
            {
                "roughness": 0.16,
                "edge_light_strength": 960.0,
                "edge_light_size": 0.34,
                "key_light_strength": 72.0,
                "fill_light_strength": 0.0,
                "environment_brightness": 0.006,
            },
            "candidate",
            ("silhouette", "rim_only"),
        ),
        (
            "tiny_bevel_fail",
            {
                "roughness": 0.26,
                "bevel_scale": 0.012,
                "edge_light_strength": 480.0,
                "edge_light_size": 0.56,
            },
            "failure_anchor",
            ("failure_anchor", "lost_edge"),
        ),
        (
            "mirror_black_fail",
            {
                "roughness": 0.012,
                "edge_light_strength": 110.0,
                "key_light_strength": 40.0,
                "fill_light_strength": 0.0,
                "environment_brightness": 0.0,
                "scratch_strength": 0.0,
            },
            "failure_anchor",
            ("failure_anchor", "black_mirror"),
        ),
        (
            "dead_matte_fail",
            {
                "roughness": 0.92,
                "specular_weight": 0.18,
                "edge_light_strength": 280.0,
                "edge_light_size": 2.6,
                "scratch_strength": 0.02,
            },
            "failure_anchor",
            ("failure_anchor", "dead_matte"),
        ),
        (
            "blown_rim_fail",
            {
                "roughness": 0.10,
                "edge_light_strength": 1650.0,
                "edge_light_size": 0.22,
                "fill_light_strength": 0.0,
                "rim_color": (1.0, 0.95, 0.72),
            },
            "failure_anchor",
            ("failure_anchor", "blown_rim"),
        ),
        (
            "scratch_noise_fail",
            {
                "roughness": 0.44,
                "scratch_strength": 0.48,
                "scratch_scale": 160.0,
                "anisotropy": 0.85,
                "edge_light_strength": 640.0,
            },
            "failure_anchor",
            ("failure_anchor", "noisy_scratches"),
        ),
    )

    variants: list[SweepVariant] = []
    for label, overrides, role, tags in cases:
        data = dict(base)
        data.update(overrides)
        data["material_lighting"] = _descriptor(data)
        variants.append(
            SweepVariant(
                name=f"{prefix}_{label}" if prefix else label,
                label=label,
                settings=data,
                note="hard-surface metal roughness, bevel, scratch, and edge-light scout",
                role=role,
                tags=("metal", "edge_light", *tags),
            )
        )
    return variants


def clear_scene() -> None:
    import bpy

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def _metal_material(settings: MetalEdgeLightSettings) -> Any:
    mat = principled_material(
        "hard surface metal study",
        settings.tint,
        roughness=settings.roughness,
        metallic=settings.metallic,
    )
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    if bsdf:
        set_node_input(bsdf, ["Specular IOR Level", "Specular"], settings.specular_weight)
        set_node_input(bsdf, ["Anisotropic IOR Level", "Anisotropic"], settings.anisotropy)
    if settings.scratch_strength > 0 and bsdf and "Normal" in bsdf.inputs:
        noise = nodes.new(type="ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = settings.scratch_scale
        noise.inputs["Detail"].default_value = 14.0
        noise.inputs["Roughness"].default_value = 0.68
        bump = nodes.new(type="ShaderNodeBump")
        bump.inputs["Strength"].default_value = settings.scratch_strength
        bump.inputs["Distance"].default_value = 0.028
        links.new(noise.outputs["Fac"], bump.inputs["Height"])
        links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def _cube(name: str, location, scale, mat: Any, rotation=(0.0, 0.0, 0.0)) -> Any:
    import bpy

    bpy.ops.mesh.primitive_cube_add(size=1, location=location, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(mat)
    return obj


def _bevel(obj: Any, width: float) -> None:
    bevel = obj.modifiers.new("highlight bevel", "BEVEL")
    bevel.width = max(0.001, width)
    bevel.segments = 8
    obj.modifiers.new("weighted normals", "WEIGHTED_NORMAL")


def _shade_smooth(obj: Any) -> None:
    import bpy

    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.shade_smooth()
    obj.select_set(False)


def _add_set(settings: MetalEdgeLightSettings) -> None:
    import bpy

    floor_mat = principled_material("metal floor", (0.18, 0.18, 0.19, 1.0), roughness=0.84)
    dark_mat = principled_material("dark metal backdrop", (0.035, 0.038, 0.044, 1.0), roughness=0.9)
    bright_mat = principled_material("bright edge backdrop", (0.76, 0.75, 0.70, 1.0), roughness=0.72)
    stripe_mat = principled_material("edge ruler stripes", (0.06, 0.065, 0.075, 1.0), roughness=0.78)

    bpy.ops.mesh.primitive_plane_add(size=5.2, location=(0, 0.14, 0))
    floor = bpy.context.object
    floor.name = "metal edge floor"
    floor.data.materials.append(floor_mat)

    _cube("dark backdrop half", (-1.22, 1.92, 1.45), (1.55, 0.03, 1.45), dark_mat)
    _cube("bright backdrop half", (1.18, 1.92, 1.45), (1.55, 0.03, 1.45), bright_mat)
    for index, x in enumerate((-1.45, -0.72, 0.0, 0.72, 1.45)):
        _cube(f"metal edge floor ruler {index}", (x, 0.42, 0.018), (0.018, 1.58, 0.012), stripe_mat)


def _add_forms(settings: MetalEdgeLightSettings) -> None:
    import bpy

    mat = _metal_material(settings)
    bevel = settings.bevel_scale

    block = _cube("bevelled hard surface block", (-0.64, 0.18, 0.56), (0.45, 0.40, 0.54), mat, rotation=(0, 0, math.radians(-6)))
    _bevel(block, bevel)

    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=0.32, depth=0.96, location=(0.32, 0.20, 0.62), rotation=(0, math.radians(90), 0))
    cyl = bpy.context.object
    cyl.name = "brushed cylinder"
    cyl.data.materials.append(mat)
    _shade_smooth(cyl)
    _bevel(cyl, bevel * 0.55)

    blade = _cube("thin edge blade", (0.95, 0.18, 0.62), (0.055, 0.58, 0.62), mat, rotation=(0.0, 0.0, math.radians(12)))
    _bevel(blade, bevel * 0.38)

    bpy.ops.mesh.primitive_uv_sphere_add(segments=40, ring_count=18, radius=0.34, location=(-1.12, 0.05, 0.48))
    curve = bpy.context.object
    curve.name = "curved contrast form"
    curve.scale = (0.72, 0.90, 0.58)
    curve.data.materials.append(mat)
    _shade_smooth(curve)


def _add_lights(settings: MetalEdgeLightSettings) -> None:
    import bpy

    bpy.ops.object.light_add(type="AREA", location=(-1.65, -2.0, 2.2))
    key = bpy.context.object
    key.name = "metal soft key"
    key.data.energy = settings.key_light_strength
    key.data.size = 2.5
    key.data.color = (1.0, 0.84, 0.66)
    look_at(key, (0.0, 0.18, 0.64))

    bpy.ops.object.light_add(type="AREA", location=(1.85, 0.92, 1.25))
    rim = bpy.context.object
    rim.name = "metal edge rim"
    rim.data.energy = settings.edge_light_strength
    rim.data.size = settings.edge_light_size
    rim.data.color = settings.rim_color
    look_at(rim, (0.10, 0.16, 0.68))

    if settings.fill_light_strength > 0:
        bpy.ops.object.light_add(type="AREA", location=(0.0, -2.2, 1.05))
        fill = bpy.context.object
        fill.name = "metal low fill"
        fill.data.energy = settings.fill_light_strength
        fill.data.size = 3.6
        fill.data.color = (0.62, 0.70, 0.86)
        look_at(fill, (0.0, 0.20, 0.55))


def _add_camera() -> None:
    add_orbit_camera(
        name=METAL_EDGE_LIGHT_CAMERA,
        target=(0.02, 0.18, 0.62),
        distance=4.1,
        lens_mm=58.0,
        yaw_degrees=-2.5,
        pitch_degrees=8.0,
    )


def build_metal_edge_light_scene(settings: MetalEdgeLightSettings | Mapping[str, Any] | None = None) -> None:
    import bpy

    metal_settings = coerce_metal_edge_light_settings(settings)
    clear_scene()
    world = bpy.context.scene.world or bpy.data.worlds.new("metal edge light world")
    bpy.context.scene.world = world
    world.color = (
        metal_settings.environment_brightness,
        metal_settings.environment_brightness,
        metal_settings.environment_brightness * 1.08,
    )
    _add_set(metal_settings)
    _add_forms(metal_settings)
    _add_lights(metal_settings)
    _add_camera()
