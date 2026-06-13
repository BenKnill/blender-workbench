from __future__ import annotations

import dataclasses
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from blender_workbench.camera import add_orbit_camera, look_at
from blender_workbench.materials import principled_material, set_node_input
from blender_workbench.sweep import SweepVariant


PROCEDURAL_TEXTURE_CAMERA = "procedural_texture_camera"


PALETTES: dict[str, tuple[tuple[float, float, float, float], tuple[float, float, float, float]]] = {
    "warm_clay": ((0.45, 0.30, 0.22, 1.0), (0.88, 0.65, 0.42, 1.0)),
    "cool_slate": ((0.18, 0.24, 0.32, 1.0), (0.64, 0.78, 0.86, 1.0)),
    "moss": ((0.18, 0.28, 0.18, 1.0), (0.66, 0.76, 0.48, 1.0)),
    "rust": ((0.30, 0.13, 0.08, 1.0), (0.92, 0.42, 0.18, 1.0)),
    "muddy_fail": ((0.24, 0.22, 0.18, 1.0), (0.42, 0.36, 0.27, 1.0)),
}


@dataclass(frozen=True)
class ProceduralTextureSettings:
    node_family: str = "noise"
    coordinate_space: str = "generated"
    texture_scale: float = 18.0
    texture_detail: float = 10.0
    texture_roughness: float = 0.58
    texture_distortion: float = 4.0
    texture_contrast: float = 0.42
    ramp_midpoint: float = 0.50
    palette: str = "warm_clay"
    palette_intensity: float = 0.72
    bump_strength: float = 0.08
    bump_distance: float = 0.08
    roughness_coupling: bool = True
    base_roughness: float = 0.68
    variation_seed: int = 0
    noise_phase: float = 0.0


def coerce_procedural_texture_settings(
    settings: ProceduralTextureSettings | Mapping[str, Any] | None = None,
) -> ProceduralTextureSettings:
    if isinstance(settings, ProceduralTextureSettings):
        return settings
    data = dataclasses.asdict(ProceduralTextureSettings())
    if settings:
        data.update({key: value for key, value in dict(settings).items() if key in data})
    return ProceduralTextureSettings(**data)


def procedural_texture_descriptor(
    settings: ProceduralTextureSettings | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    values = coerce_procedural_texture_settings(settings)
    return {
        "node_family": values.node_family,
        "coordinate_space": values.coordinate_space,
        "scale": values.texture_scale,
        "contrast": values.texture_contrast,
        "ramp_midpoint": values.ramp_midpoint,
        "palette": values.palette,
        "palette_intensity": values.palette_intensity,
        "bump_strength": values.bump_strength,
        "bump_distance": values.bump_distance,
        "roughness_coupling": values.roughness_coupling,
        "variation_seed": values.variation_seed,
        "noise_phase": values.noise_phase,
    }


def _case(base: Mapping[str, Any], overrides: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(base)
    data.update(overrides)
    data["node_descriptor"] = procedural_texture_descriptor(data)
    return data


def procedural_texture_variants(
    *,
    prefix: str = "ptex",
    center_scale: float = 18.0,
    scale_stride: float = 3.0,
    contrast_stride: float = 0.24,
    bump_stride: float = 0.08,
    palette_intensity_stride: float = 0.18,
) -> list[SweepVariant]:
    """Build a surface texture-node case board with editable stride knobs."""
    base = dataclasses.asdict(ProceduralTextureSettings(texture_scale=center_scale))
    fine_scale = center_scale * scale_stride
    broad_scale = center_scale / max(0.1, scale_stride)
    marked_contrast = 0.42 + contrast_stride
    over_contrast = min(1.25, 0.42 + contrast_stride * 2.4)
    marked_bump = 0.08 + bump_stride
    hard_bump = min(0.55, 0.08 + bump_stride * 3.4)
    rich_palette = min(1.0, 0.72 + palette_intensity_stride)
    flat_palette = max(0.10, 0.72 - palette_intensity_stride * 2.5)

    cases: tuple[tuple[str, Mapping[str, Any], str, tuple[str, ...]], ...] = (
        (
            "noise_fine_subtle",
            {
                "node_family": "noise",
                "texture_scale": fine_scale,
                "texture_contrast": 0.18,
                "bump_strength": 0.02,
                "palette": "warm_clay",
                "palette_intensity": 0.48,
            },
            "candidate",
            ("noise", "fine"),
        ),
        (
            "noise_medium_marked",
            {
                "node_family": "noise",
                "texture_scale": center_scale,
                "texture_contrast": marked_contrast,
                "bump_strength": marked_bump,
                "palette": "warm_clay",
                "palette_intensity": rich_palette,
            },
            "candidate",
            ("noise", "marked"),
        ),
        (
            "noise_broad_marked",
            {
                "node_family": "noise",
                "texture_scale": broad_scale,
                "texture_contrast": marked_contrast,
                "bump_strength": marked_bump,
                "palette": "cool_slate",
                "palette_intensity": rich_palette,
            },
            "candidate",
            ("noise", "broad"),
        ),
        (
            "wave_medium_ridges",
            {
                "node_family": "wave",
                "texture_scale": center_scale * 0.72,
                "texture_distortion": 7.0,
                "texture_contrast": marked_contrast,
                "bump_strength": marked_bump * 1.2,
                "palette": "moss",
                "coordinate_space": "object",
            },
            "candidate",
            ("wave", "ridges"),
        ),
        (
            "voronoi_cells",
            {
                "node_family": "voronoi",
                "texture_scale": center_scale * 0.42,
                "texture_contrast": marked_contrast,
                "bump_strength": marked_bump,
                "palette": "rust",
                "coordinate_space": "object",
            },
            "candidate",
            ("voronoi", "cells"),
        ),
        (
            "roughness_coupled",
            {
                "node_family": "noise",
                "texture_scale": center_scale * 1.25,
                "texture_contrast": marked_contrast,
                "bump_strength": marked_bump,
                "palette": "cool_slate",
                "roughness_coupling": True,
                "base_roughness": 0.54,
            },
            "candidate",
            ("roughness_coupled",),
        ),
        (
            "roughness_decoupled",
            {
                "node_family": "noise",
                "texture_scale": center_scale * 1.25,
                "texture_contrast": marked_contrast,
                "bump_strength": marked_bump,
                "palette": "cool_slate",
                "roughness_coupling": False,
                "base_roughness": 0.70,
            },
            "candidate",
            ("roughness_decoupled",),
        ),
        (
            "fine_unreadable_fail",
            {
                "node_family": "noise",
                "texture_scale": fine_scale * 2.2,
                "texture_contrast": 0.16,
                "bump_strength": 0.01,
                "palette_intensity": flat_palette,
            },
            "failure_anchor",
            ("failure_anchor", "too_fine"),
        ),
        (
            "broad_lighting_fail",
            {
                "node_family": "noise",
                "texture_scale": broad_scale * 0.38,
                "texture_contrast": over_contrast,
                "bump_strength": marked_bump,
                "palette": "cool_slate",
            },
            "failure_anchor",
            ("failure_anchor", "too_broad"),
        ),
        (
            "bump_destroyed_fail",
            {
                "node_family": "voronoi",
                "texture_scale": center_scale,
                "texture_contrast": over_contrast,
                "bump_strength": hard_bump,
                "bump_distance": 0.18,
                "palette": "rust",
            },
            "failure_anchor",
            ("failure_anchor", "over_bumped"),
        ),
        (
            "muddy_palette_fail",
            {
                "node_family": "wave",
                "texture_scale": center_scale * 0.8,
                "texture_contrast": 0.20,
                "bump_strength": 0.04,
                "palette": "muddy_fail",
                "palette_intensity": flat_palette,
                "roughness_coupling": False,
            },
            "failure_anchor",
            ("failure_anchor", "muddy_palette"),
        ),
    )

    variants: list[SweepVariant] = []
    for label, overrides, role, tags in cases:
        variants.append(
            SweepVariant(
                name=f"{prefix}_{label}" if prefix else label,
                label=label,
                settings=_case(base, overrides),
                note="procedural surface texture-node scout: family, scale, ramp, palette, bump, roughness",
                role=role,
                tags=("procedural_texture", "surface_shader", *tags),
                procedural_controls={"variation_seed": overrides.get("variation_seed", base["variation_seed"])},
            )
        )
    return variants


def clear_scene() -> None:
    import bpy

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _palette_colors(settings: ProceduralTextureSettings):
    low, high = PALETTES.get(settings.palette, PALETTES["warm_clay"])
    intensity = _clamp01(settings.palette_intensity)
    neutral = (0.50, 0.50, 0.50, 1.0)
    return (
        tuple(neutral[index] * (1.0 - intensity) + low[index] * intensity for index in range(4)),
        tuple(neutral[index] * (1.0 - intensity) + high[index] * intensity for index in range(4)),
    )


def _texture_output(node: Any) -> Any:
    for name in ("Fac", "Distance", "Color"):
        if name in node.outputs:
            return node.outputs[name]
    return next(iter(node.outputs))


def _set_if_input(node: Any, name: str, value: Any) -> None:
    if name in node.inputs:
        node.inputs[name].default_value = value


def _texture_node(nodes: Any, settings: ProceduralTextureSettings) -> Any:
    family = settings.node_family.lower()
    if family == "wave":
        node = nodes.new(type="ShaderNodeTexWave")
        _set_if_input(node, "Scale", settings.texture_scale)
        _set_if_input(node, "Distortion", settings.texture_distortion)
        return node
    if family == "voronoi":
        node = nodes.new(type="ShaderNodeTexVoronoi")
        _set_if_input(node, "Scale", settings.texture_scale)
        _set_if_input(node, "Randomness", 0.62 + (settings.variation_seed % 5) * 0.06)
        return node
    node = nodes.new(type="ShaderNodeTexNoise")
    if hasattr(node, "noise_dimensions"):
        node.noise_dimensions = "4D"
    _set_if_input(node, "Scale", settings.texture_scale)
    _set_if_input(node, "Detail", settings.texture_detail)
    _set_if_input(node, "Roughness", settings.texture_roughness)
    _set_if_input(node, "W", float(settings.noise_phase) + settings.variation_seed * 0.17)
    return node


def _link_coordinate_space(nodes: Any, links: Any, texture: Any, settings: ProceduralTextureSettings) -> None:
    if "Vector" not in texture.inputs:
        return
    coord = nodes.new(type="ShaderNodeTexCoord")
    key = "Object" if settings.coordinate_space == "object" else "Generated"
    if key in coord.outputs:
        links.new(coord.outputs[key], texture.inputs["Vector"])


def procedural_texture_material(settings: ProceduralTextureSettings | Mapping[str, Any] | None = None) -> Any:
    values = coerce_procedural_texture_settings(settings)
    mat = principled_material("procedural texture study material", (0.62, 0.50, 0.42, 1.0), roughness=values.base_roughness)
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    if not bsdf:
        return mat

    texture = _texture_node(nodes, values)
    _link_coordinate_space(nodes, links, texture, values)
    ramp = nodes.new(type="ShaderNodeValToRGB")
    contrast = max(0.0, values.texture_contrast)
    low_pos = _clamp01(values.ramp_midpoint - 0.18 - contrast * 0.18)
    high_pos = _clamp01(values.ramp_midpoint + 0.18 + contrast * 0.18)
    low_color, high_color = _palette_colors(values)
    ramp.color_ramp.elements[0].position = low_pos
    ramp.color_ramp.elements[0].color = low_color
    ramp.color_ramp.elements[1].position = max(low_pos + 0.02, high_pos)
    ramp.color_ramp.elements[1].color = high_color
    links.new(_texture_output(texture), ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])

    if values.bump_strength > 0 and "Normal" in bsdf.inputs:
        bump = nodes.new(type="ShaderNodeBump")
        bump.inputs["Strength"].default_value = values.bump_strength
        bump.inputs["Distance"].default_value = values.bump_distance
        links.new(_texture_output(texture), bump.inputs["Height"])
        links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])

    roughness = values.base_roughness
    if values.roughness_coupling:
        roughness = max(0.18, min(0.92, values.base_roughness + values.texture_contrast * 0.12 - values.bump_strength * 0.22))
    set_node_input(bsdf, ["Roughness"], roughness)
    return mat


def _shade_smooth(obj: Any) -> None:
    import bpy

    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.shade_smooth()
    obj.select_set(False)


def _cube(name: str, location, scale, mat: Any) -> Any:
    import bpy

    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(mat)
    return obj


def _add_set() -> None:
    import bpy

    floor_mat = principled_material("procedural texture floor", (0.20, 0.20, 0.21, 1.0), roughness=0.88)
    wall_mat = principled_material("procedural texture wall", (0.12, 0.14, 0.17, 1.0), roughness=0.92)
    stripe_mat = principled_material("frequency scale stripes", (0.04, 0.045, 0.05, 1.0), roughness=0.78)
    card_mat = principled_material("neutral value cards", (0.70, 0.69, 0.64, 1.0), roughness=0.52)

    bpy.ops.mesh.primitive_plane_add(size=4.8, location=(0, 0.18, 0))
    floor = bpy.context.object
    floor.name = "procedural texture floor"
    floor.data.materials.append(floor_mat)

    bpy.ops.mesh.primitive_plane_add(size=4.8, location=(0, 1.78, 1.65), rotation=(math.pi / 2, 0, 0))
    wall = bpy.context.object
    wall.name = "procedural texture backdrop"
    wall.data.materials.append(wall_mat)

    for index, x in enumerate((-1.45, -0.78, 0.0, 0.78, 1.45)):
        _cube(f"texture frequency ruler {index}", (x, 0.32, 0.018), (0.020, 1.62, 0.012), stripe_mat)
    for index, x in enumerate((-1.24, 1.24)):
        _cube(f"neutral color card {index}", (x, 1.74, 1.04), (0.14, 0.018, 0.74), card_mat)


def _add_subject(settings: ProceduralTextureSettings) -> None:
    import bpy

    mat = procedural_texture_material(settings)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=56, ring_count=28, radius=0.74, location=(-0.26, 0.22, 0.82))
    sphere = bpy.context.object
    sphere.name = "procedural texture sphere"
    sphere.scale = (0.90, 0.90, 0.74)
    sphere.data.materials.append(mat)
    _shade_smooth(sphere)

    bpy.ops.mesh.primitive_cube_add(size=1, location=(0.82, 0.15, 0.58), rotation=(0.0, 0.0, math.radians(-9.0)))
    block = bpy.context.object
    block.name = "procedural texture angled slab"
    block.scale = (0.34, 0.48, 0.46)
    block.data.materials.append(mat)
    bevel = block.modifiers.new("texture slab bevel", "BEVEL")
    bevel.width = 0.08
    bevel.segments = 6
    block.modifiers.new("weighted normal", "WEIGHTED_NORMAL")


def _add_lights() -> None:
    import bpy

    bpy.ops.object.light_add(type="AREA", location=(-1.6, -2.2, 2.3))
    key = bpy.context.object
    key.name = "procedural texture broad key"
    key.data.energy = 360
    key.data.size = 3.0
    key.data.color = (1.0, 0.86, 0.70)
    look_at(key, (0.0, 0.22, 0.76))

    bpy.ops.object.light_add(type="AREA", location=(1.8, -1.1, 1.45))
    rake = bpy.context.object
    rake.name = "procedural texture grazing bump light"
    rake.data.energy = 190
    rake.data.size = 0.85
    rake.data.color = (0.78, 0.86, 1.0)
    look_at(rake, (0.25, 0.18, 0.62))


def _add_camera() -> None:
    add_orbit_camera(
        name=PROCEDURAL_TEXTURE_CAMERA,
        target=(0.10, 0.22, 0.74),
        distance=3.85,
        lens_mm=58.0,
        yaw_degrees=0.0,
        pitch_degrees=9.0,
    )


def build_procedural_texture_scene(settings: ProceduralTextureSettings | Mapping[str, Any] | None = None) -> None:
    import bpy

    texture_settings = coerce_procedural_texture_settings(settings)
    clear_scene()
    world = bpy.context.scene.world or bpy.data.worlds.new("procedural texture world")
    bpy.context.scene.world = world
    world.color = (0.018, 0.019, 0.022)
    _add_set()
    _add_subject(texture_settings)
    _add_lights()
    _add_camera()
