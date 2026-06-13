"""Reusable helpers for Blender parameter-sweep visual workbenches."""

from .camera import add_orbit_camera, camera_distance_for_matching_framing, look_at, orbit_location
from .presets import RENDER_PRESETS, SWEEP_AXES, TILE_PRESETS, SweepAxis, one_axis_variants, stride_axis, two_axis_variants
from .primitives import add_soft_horizon_band, soft_band_alpha_profile
from .promote import import_recipe_callable, load_sweep_variants, promote_from_metadata, select_metadata_variant
from .sweep import (
    RenderConfig,
    RenderResult,
    SweepVariant,
    TileSpec,
    configure_render,
    grid_variants,
    named_variants,
    render_selected_variant,
    render_sweep,
    select_variant,
)

__all__ = [
    "add_orbit_camera",
    "add_soft_horizon_band",
    "camera_distance_for_matching_framing",
    "RenderConfig",
    "RenderResult",
    "RENDER_PRESETS",
    "SWEEP_AXES",
    "SweepAxis",
    "SweepVariant",
    "TILE_PRESETS",
    "TileSpec",
    "configure_render",
    "grid_variants",
    "import_recipe_callable",
    "load_sweep_variants",
    "look_at",
    "named_variants",
    "one_axis_variants",
    "orbit_location",
    "promote_from_metadata",
    "render_selected_variant",
    "render_sweep",
    "select_metadata_variant",
    "select_variant",
    "soft_band_alpha_profile",
    "stride_axis",
    "two_axis_variants",
]
