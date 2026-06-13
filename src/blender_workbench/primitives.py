from __future__ import annotations

import math
from typing import Any


def soft_band_alpha_profile(alpha: float, feather_steps: int = 4, *, falloff_power: float = 1.7) -> tuple[float, ...]:
    """Return symmetric alpha values for a feathered light or haze band."""
    if not 0.0 <= alpha <= 1.0:
        raise ValueError(f"alpha must be in [0, 1], got {alpha!r}")
    if feather_steps < 0:
        raise ValueError(f"feather_steps must be >= 0, got {feather_steps!r}")
    if feather_steps == 0:
        return (alpha,)

    edge_values = []
    for index in range(feather_steps):
        t = (index + 1) / (feather_steps + 1)
        edge_values.append(alpha * (t**falloff_power))
    return (*edge_values, alpha, *reversed(edge_values))


def _soft_band_material(
    name: str,
    color,
    strength: float,
    alpha: float,
    center_fraction: float,
    noise_strength: float,
    noise_scale: float,
):
    import bpy

    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.blend_method = "BLEND"
    mat.use_screen_refraction = True
    nodes = mat.node_tree.nodes
    nodes.clear()

    coord = nodes.new(type="ShaderNodeTexCoord")
    separate = nodes.new(type="ShaderNodeSeparateXYZ")
    ramp = nodes.new(type="ShaderNodeValToRGB")
    lower = max(0.02, 0.5 - center_fraction * 0.5)
    upper = min(0.98, 0.5 + center_fraction * 0.5)
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
    ramp.color_ramp.elements[1].position = 1.0
    ramp.color_ramp.elements[1].color = (0.0, 0.0, 0.0, 1.0)
    left = ramp.color_ramp.elements.new(lower)
    left.color = (alpha, alpha, alpha, 1.0)
    right = ramp.color_ramp.elements.new(upper)
    right.color = (alpha, alpha, alpha, 1.0)

    transparent = nodes.new(type="ShaderNodeBsdfTransparent")
    emission = nodes.new(type="ShaderNodeEmission")
    emission.inputs["Color"].default_value = color
    emission.inputs["Strength"].default_value = strength
    mix = nodes.new(type="ShaderNodeMixShader")
    out = nodes.new(type="ShaderNodeOutputMaterial")

    mat.node_tree.links.new(coord.outputs["Generated"], separate.inputs["Vector"])
    mat.node_tree.links.new(separate.outputs["Y"], ramp.inputs["Fac"])
    if noise_strength > 0:
        try:
            split_color = nodes.new(type="ShaderNodeSeparateColor")
            base_value = split_color.outputs["Red"]
        except RuntimeError:
            split_color = nodes.new(type="ShaderNodeSeparateRGB")
            base_value = split_color.outputs["R"]
        noise = nodes.new(type="ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = noise_scale
        noise.inputs["Detail"].default_value = 7.0
        noise.inputs["Roughness"].default_value = 0.62
        center_noise = nodes.new(type="ShaderNodeMath")
        center_noise.operation = "SUBTRACT"
        center_noise.inputs[1].default_value = 0.5
        scale_noise = nodes.new(type="ShaderNodeMath")
        scale_noise.operation = "MULTIPLY"
        scale_noise.inputs[1].default_value = noise_strength
        add_noise = nodes.new(type="ShaderNodeMath")
        add_noise.operation = "ADD"
        add_noise.use_clamp = True
        mat.node_tree.links.new(ramp.outputs["Color"], split_color.inputs[0])
        mat.node_tree.links.new(base_value, add_noise.inputs[0])
        mat.node_tree.links.new(noise.outputs["Fac"], center_noise.inputs[0])
        mat.node_tree.links.new(center_noise.outputs[0], scale_noise.inputs[0])
        mat.node_tree.links.new(scale_noise.outputs[0], add_noise.inputs[1])
        mat.node_tree.links.new(add_noise.outputs[0], mix.inputs["Fac"])
    else:
        mat.node_tree.links.new(ramp.outputs["Color"], mix.inputs["Fac"])
    mat.node_tree.links.new(transparent.outputs["BSDF"], mix.inputs[1])
    mat.node_tree.links.new(emission.outputs["Emission"], mix.inputs[2])
    mat.node_tree.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return mat


def add_soft_horizon_band(
    *,
    name: str,
    location: tuple[float, float, float],
    width: float,
    height: float,
    color,
    strength: float,
    alpha: float = 0.55,
    feather_steps: int = 4,
    center_fraction: float = 0.34,
    noise_strength: float = 0.0,
    noise_scale: float = 7.0,
) -> list[Any]:
    """Add a feathered vertical light card with generated-coordinate alpha.

    This avoids hard card edges in selected renders without requiring compositor
    nodes or simulations.
    """
    import bpy

    soft_band_alpha_profile(alpha, feather_steps)
    center_fraction = center_fraction / (1.0 + max(0, feather_steps) * 0.12)
    center_fraction = max(0.05, min(0.9, center_fraction))
    noise_strength = max(0.0, min(0.75, noise_strength))
    noise_scale = max(0.1, noise_scale)
    mat = _soft_band_material(f"{name} soft gradient material", color, strength, alpha, center_fraction, noise_strength, noise_scale)
    bpy.ops.mesh.primitive_plane_add(size=1, location=location, rotation=(math.pi / 2, 0, 0))
    band = bpy.context.object
    band.name = name
    band.scale = (width, height, 1.0)
    band.data.materials.append(mat)
    if hasattr(band, "visible_shadow"):
        band.visible_shadow = False
    return [band]
