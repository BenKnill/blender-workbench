"""Reusable helpers for Blender parameter-sweep visual workbenches."""

from .camera import add_orbit_camera, camera_distance_for_matching_framing, look_at, orbit_location
from .capabilities import collect_capability_report, expand_required_tools, format_capability_report
from .example_manifest import ExamplePreflight, format_preflight_report, load_manifest, preflight_examples
from .example_pick_smoke import PickSmokePlan, PickSmokeResult, pick_smoke_plans, run_pick_smoke, verify_selected_json
from .postprocess import (
    PostprocessLookSettings,
    coerce_postprocess_look_settings,
    magick_look_postprocess,
    postprocess_look_variants,
    render_postprocess_sweep,
)
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
    render_selected_from_sweep,
    render_selected_variant,
    render_sweep,
    select_variant,
    variants_from_sweep_metadata,
)

__all__ = [
    "add_orbit_camera",
    "add_soft_horizon_band",
    "camera_distance_for_matching_framing",
    "collect_capability_report",
    "coerce_postprocess_look_settings",
    "ExamplePreflight",
    "format_preflight_report",
    "format_capability_report",
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
    "expand_required_tools",
    "import_recipe_callable",
    "load_manifest",
    "load_sweep_variants",
    "look_at",
    "named_variants",
    "one_axis_variants",
    "orbit_location",
    "PickSmokePlan",
    "PickSmokeResult",
    "pick_smoke_plans",
    "magick_look_postprocess",
    "PostprocessLookSettings",
    "postprocess_look_variants",
    "render_postprocess_sweep",
    "promote_from_metadata",
    "preflight_examples",
    "render_selected_from_sweep",
    "render_selected_variant",
    "render_sweep",
    "run_pick_smoke",
    "select_metadata_variant",
    "select_variant",
    "soft_band_alpha_profile",
    "stride_axis",
    "two_axis_variants",
    "variants_from_sweep_metadata",
    "verify_selected_json",
]
