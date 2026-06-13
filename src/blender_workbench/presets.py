from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .sweep import RenderConfig, SweepVariant, TileSpec, grid_variants


@dataclass(frozen=True)
class SweepAxis:
    name: str
    values: tuple[tuple[str, Mapping[str, Any]], ...]
    note: str = ""


def one_axis_variants(
    axis: SweepAxis,
    *,
    base: Mapping[str, Any] | None = None,
    prefix: str | None = None,
) -> list[SweepVariant]:
    base_data = dict(base or {})
    variants: list[SweepVariant] = []
    for label, settings in axis.values:
        data = dict(base_data)
        data.update(settings)
        name = f"{prefix}_{label}" if prefix else label
        variants.append(SweepVariant(name=name, label=label, settings=data, note=axis.note or None))
    return variants


def two_axis_variants(
    row_axis: SweepAxis,
    column_axis: SweepAxis,
    *,
    base: Mapping[str, Any] | None = None,
    prefix: str | None = None,
) -> list[SweepVariant]:
    variants = grid_variants(row_axis.values, column_axis.values, base=base)
    if not prefix:
        return variants
    return [
        SweepVariant(
            name=f"{prefix}_{variant.name}",
            label=variant.label,
            settings=variant.settings,
            note=variant.note,
        )
        for variant in variants
    ]


PLUME_ALPHA_STRENGTH = SweepAxis(
    name="plume_alpha_strength",
    note="thin transparent shells usually read more like vacuum plume than fire",
    values=(
        ("ghost", {"shell_alpha": 0.015, "shell_strength": 0.38, "filament_alpha": 0.12, "filament_strength": 0.65}),
        ("balanced", {"shell_alpha": 0.035, "shell_strength": 0.55, "filament_alpha": 0.18, "filament_strength": 0.85}),
        ("solid_fail", {"shell_alpha": 0.16, "shell_strength": 0.80, "filament_alpha": 0.08, "filament_strength": 0.45}),
    ),
)

PLUME_SHAPE = SweepAxis(
    name="plume_shape",
    note="wide, soft, structured plumes beat narrow torch shapes for upper-stage vacuum scenes",
    values=(
        ("needle", {"width": 0.75, "length": 1.15, "filament_count": 18}),
        ("bell", {"width": 1.25, "length": 1.0, "filament_count": 28}),
        ("fan", {"width": 1.75, "length": 0.82, "filament_count": 42}),
    ),
)

SUNSET_HAZE = SweepAxis(
    name="sunset_haze",
    note="separate horizon color from haze density so long-exposure skies do not become one flat gradient",
    values=(
        ("violet_dust", {"sky_color": (0.22, 0.18, 0.34), "horizon_color": (0.92, 0.34, 0.18), "haze_density": 0.018}),
        ("peach_moonrise", {"sky_color": (0.30, 0.28, 0.45), "horizon_color": (1.0, 0.56, 0.24), "haze_density": 0.032}),
        ("blue_afterglow", {"sky_color": (0.08, 0.12, 0.22), "horizon_color": (0.55, 0.34, 0.42), "haze_density": 0.012}),
    ),
)

SUBSURFACE_CANDY = SweepAxis(
    name="subsurface_candy",
    note="push radius and color together when testing wax, skin, jelly, or moonlit translucency",
    values=(
        ("opal", {"subsurface_weight": 0.25, "subsurface_radius": (1.0, 0.55, 0.28), "subsurface_color": (0.78, 0.92, 1.0, 1)}),
        ("amber", {"subsurface_weight": 0.45, "subsurface_radius": (1.0, 0.35, 0.12), "subsurface_color": (1.0, 0.56, 0.20, 1)}),
        ("ruby", {"subsurface_weight": 0.6, "subsurface_radius": (1.0, 0.18, 0.08), "subsurface_color": (1.0, 0.10, 0.08, 1)}),
    ),
)

CAUSTIC_WATER = SweepAxis(
    name="caustic_water",
    note="caustic tests need both pattern scale and water roughness, not just brighter lights",
    values=(
        ("tight_ripples", {"caustic_scale": 18.0, "water_roughness": 0.025, "caustic_strength": 0.7}),
        ("pool", {"caustic_scale": 8.0, "water_roughness": 0.055, "caustic_strength": 1.0}),
        ("storm_glass", {"caustic_scale": 3.5, "water_roughness": 0.12, "caustic_strength": 1.35}),
    ),
)

SILHOUETTE_SHAPE = SweepAxis(
    name="silhouette_shape",
    note="shape sweeps should test readable outline before material polish",
    values=(
        ("spindly", {"primary_scale": (0.7, 0.7, 1.35), "secondary_scale": (0.35, 0.35, 1.5)}),
        ("blocky", {"primary_scale": (1.05, 0.85, 0.95), "secondary_scale": (0.7, 0.55, 0.85)}),
        ("swept", {"primary_scale": (0.85, 1.25, 1.0), "secondary_scale": (0.42, 1.45, 0.75)}),
    ),
)

SWEEP_AXES = {
    axis.name: axis
    for axis in [
        PLUME_ALPHA_STRENGTH,
        PLUME_SHAPE,
        SUNSET_HAZE,
        SUBSURFACE_CANDY,
        CAUSTIC_WATER,
        SILHOUETTE_SHAPE,
    ]
}

TILE_PRESETS = {
    "hero_pair": TileSpec.hero_pair(),
    "balanced_grid": TileSpec.balanced_grid(),
    "micro_grid": TileSpec.micro_grid(),
    "square_moodboard": TileSpec.square_moodboard(),
    "filmstrip": TileSpec.filmstrip(),
}

RENDER_PRESETS = {
    "shape_scout": RenderConfig.shape_scout(),
    "material_scout": RenderConfig.material_scout(),
    "cycles_preview": RenderConfig.cycles_preview(),
    "hero_check": RenderConfig.hero_check(),
}
