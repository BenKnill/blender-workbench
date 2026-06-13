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


def principled_material(
    name: str,
    color,
    *,
    roughness: float = 0.8,
    metallic: float = 0.0,
    alpha: float = 1.0,
    emission=None,
    emission_strength: float = 0.0,
):
    bpy = _bpy()
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.blend_method = "BLEND" if alpha < 1.0 else "OPAQUE"

    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        set_node_input(bsdf, ["Base Color"], color)
        set_node_input(bsdf, ["Roughness"], roughness)
        set_node_input(bsdf, ["Metallic"], metallic)
        set_node_input(bsdf, ["Alpha"], alpha)
        if emission is not None:
            set_node_input(bsdf, ["Emission Color", "Emission"], emission)
            set_node_input(bsdf, ["Emission Strength"], emission_strength)
    return mat

