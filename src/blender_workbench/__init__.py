"""Reusable helpers for Blender parameter-sweep visual workbenches."""

from .artifact_index import (
    ArtifactDescriptor,
    build_artifact_index,
    format_artifact_report,
    scan_artifacts,
    validate_artifact_index,
)
from .artifact_fingerprint import fingerprint_status, make_artifact_fingerprint, render_cache_fingerprint
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
from .promotion_status import PromotionStatus, format_promotion_report, promotion_statuses
from .review_page import write_review_page
from .sweep import (
    RenderConfig,
    RenderResult,
    SweepVariant,
    TileSpec,
    VARIANT_ROLES,
    configure_render,
    grid_variants,
    named_variants,
    normalize_variant_role,
    normalize_variant_tags,
    PROTECTED_PROMOTION_ROLES,
    render_selected_from_sweep,
    render_selected_variant,
    render_sweep,
    select_variant,
    variants_from_sweep_metadata,
)

__all__ = [
    "add_orbit_camera",
    "add_soft_horizon_band",
    "ArtifactDescriptor",
    "build_artifact_index",
    "camera_distance_for_matching_framing",
    "fingerprint_status",
    "collect_capability_report",
    "coerce_postprocess_look_settings",
    "ExamplePreflight",
    "format_artifact_report",
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
    "VARIANT_ROLES",
    "configure_render",
    "grid_variants",
    "expand_required_tools",
    "import_recipe_callable",
    "load_manifest",
    "load_sweep_variants",
    "look_at",
    "make_artifact_fingerprint",
    "named_variants",
    "normalize_variant_role",
    "normalize_variant_tags",
    "one_axis_variants",
    "orbit_location",
    "PickSmokePlan",
    "PickSmokeResult",
    "pick_smoke_plans",
    "magick_look_postprocess",
    "PostprocessLookSettings",
    "PROTECTED_PROMOTION_ROLES",
    "postprocess_look_variants",
    "render_postprocess_sweep",
    "render_cache_fingerprint",
    "promote_from_metadata",
    "PromotionStatus",
    "format_promotion_report",
    "promotion_statuses",
    "preflight_examples",
    "render_selected_from_sweep",
    "render_selected_variant",
    "render_sweep",
    "run_pick_smoke",
    "scan_artifacts",
    "select_metadata_variant",
    "select_variant",
    "soft_band_alpha_profile",
    "stride_axis",
    "two_axis_variants",
    "validate_artifact_index",
    "variants_from_sweep_metadata",
    "verify_selected_json",
    "write_review_page",
]
