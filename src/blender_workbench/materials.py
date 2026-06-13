from __future__ import annotations

from typing import Any


def _bpy() -> Any:
    import bpy

    return bpy


def set_node_input(node: Any, names: list[str], value: Any) -> bool:
    for name in names:
        if name in node.inputs:
            node.inputs[name].default_value = value
            return True
    return False


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _scaled_color(color, amount: float):
    return (
        _clamp01(color[0] * amount),
        _clamp01(color[1] * amount),
        _clamp01(color[2] * amount),
        color[3] if len(color) > 3 else 1.0,
    )


def transparent_emission_material(name: str, color, strength: float, alpha: float):
    """Create a transparent/emissive material.

    Alpha semantics are intentionally plain:
    - alpha=0.0 means fully transparent
    - alpha=1.0 means fully emissive

    This prevents the inverted-alpha bug that can make sweeps lie.
    """
    if not 0.0 <= alpha <= 1.0:
        raise ValueError(f"alpha must be in [0, 1], got {alpha!r}")

    bpy = _bpy()
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.blend_method = "BLEND"
    mat.use_screen_refraction = True

    nodes = mat.node_tree.nodes
    nodes.clear()
    transparent = nodes.new(type="ShaderNodeBsdfTransparent")
    emission = nodes.new(type="ShaderNodeEmission")
    emission.inputs["Color"].default_value = color
    emission.inputs["Strength"].default_value = strength
    mix = nodes.new(type="ShaderNodeMixShader")
    mix.inputs["Fac"].default_value = alpha
    out = nodes.new(type="ShaderNodeOutputMaterial")

    mat.node_tree.links.new(transparent.outputs["BSDF"], mix.inputs[1])
    mat.node_tree.links.new(emission.outputs["Emission"], mix.inputs[2])
    mat.node_tree.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return mat


def textured_transparent_emission_material(
    name: str,
    color,
    strength: float,
    alpha: float,
    *,
    texture_magnitude: float = 0.0,
    texture_scale: float = 12.0,
    texture_detail: float = 8.0,
    texture_roughness: float = 0.55,
):
    """Create transparent emission with procedural color variation.

    Keep alpha semantics identical to `transparent_emission_material`.
    Texture magnitude controls contrast around the base emission color.
    """
    if texture_magnitude <= 0:
        return transparent_emission_material(name, color, strength, alpha)
    if not 0.0 <= alpha <= 1.0:
        raise ValueError(f"alpha must be in [0, 1], got {alpha!r}")

    bpy = _bpy()
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.blend_method = "BLEND"
    mat.use_screen_refraction = True

    nodes = mat.node_tree.nodes
    nodes.clear()
    transparent = nodes.new(type="ShaderNodeBsdfTransparent")
    emission = nodes.new(type="ShaderNodeEmission")
    emission.inputs["Strength"].default_value = strength

    noise = nodes.new(type="ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = texture_scale
    noise.inputs["Detail"].default_value = texture_detail
    noise.inputs["Roughness"].default_value = texture_roughness

    ramp = nodes.new(type="ShaderNodeValToRGB")
    contrast = max(0.0, texture_magnitude)
    ramp.color_ramp.elements[0].position = _clamp01(0.48 - contrast * 0.22)
    ramp.color_ramp.elements[0].color = _scaled_color(color, max(0.0, 1.0 - contrast * 0.72))
    ramp.color_ramp.elements[1].position = _clamp01(0.52 + contrast * 0.20)
    ramp.color_ramp.elements[1].color = _scaled_color(color, 1.0 + contrast * 0.95)

    mix = nodes.new(type="ShaderNodeMixShader")
    mix.inputs["Fac"].default_value = alpha
    out = nodes.new(type="ShaderNodeOutputMaterial")

    mat.node_tree.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    mat.node_tree.links.new(ramp.outputs["Color"], emission.inputs["Color"])
    mat.node_tree.links.new(transparent.outputs["BSDF"], mix.inputs[1])
    mat.node_tree.links.new(emission.outputs["Emission"], mix.inputs[2])
    mat.node_tree.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return mat


def emission_material(name: str, color, strength: float):
    bpy = _bpy()
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True

    nodes = mat.node_tree.nodes
    nodes.clear()
    emission = nodes.new(type="ShaderNodeEmission")
    emission.inputs["Color"].default_value = color
    emission.inputs["Strength"].default_value = strength
    out = nodes.new(type="ShaderNodeOutputMaterial")
    mat.node_tree.links.new(emission.outputs["Emission"], out.inputs["Surface"])
    return mat


def principled_material(
    name: str,
    color,
    *,
    roughness: float = 0.8,
    metallic: float = 0.0,
    ior: float = 1.45,
    alpha: float = 1.0,
    subsurface_weight: float = 0.0,
    subsurface_radius=None,
    subsurface_scale: float | None = None,
    transmission_weight: float = 0.0,
    emission=None,
    emission_strength: float = 0.0,
):
    bpy = _bpy()
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.blend_method = "BLEND" if alpha < 1.0 else "OPAQUE"
    if alpha < 1.0 or transmission_weight > 0:
        mat.use_screen_refraction = True

    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        set_node_input(bsdf, ["Base Color"], color)
        set_node_input(bsdf, ["Roughness"], roughness)
        set_node_input(bsdf, ["Metallic"], metallic)
        set_node_input(bsdf, ["IOR"], ior)
        set_node_input(bsdf, ["Alpha"], alpha)
        set_node_input(bsdf, ["Subsurface Weight"], subsurface_weight)
        if subsurface_radius is not None:
            set_node_input(bsdf, ["Subsurface Radius"], subsurface_radius)
        if subsurface_scale is not None:
            set_node_input(bsdf, ["Subsurface Scale"], subsurface_scale)
        set_node_input(bsdf, ["Transmission Weight"], transmission_weight)
        if emission is not None:
            set_node_input(bsdf, ["Emission Color", "Emission"], emission)
            set_node_input(bsdf, ["Emission Strength"], emission_strength)
    return mat
