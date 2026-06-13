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


def stride_axis(
    name: str,
    parameter: str,
    *,
    center: float,
    stride: float,
    steps: tuple[int, ...] = (-2, -1, 0, 1, 2),
    clamp_min: float | None = None,
    clamp_max: float | None = None,
    note: str = "",
) -> SweepAxis:
    """Build an axis around a center value with an editable stride.

    This is useful when an early sheet looks timid: double `stride` and rerun
    without rewriting a pile of named cases.
    """
    values: list[tuple[str, Mapping[str, Any]]] = []
    for step in steps:
        value = center + step * stride
        if clamp_min is not None:
            value = max(clamp_min, value)
        if clamp_max is not None:
            value = min(clamp_max, value)
        label = "base" if step == 0 else f"{'p' if step > 0 else 'm'}{abs(step)}"
        values.append((label, {parameter: value}))
    return SweepAxis(name=name, values=tuple(values), note=note)


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

LIGHT_SOURCE_JITTER = SweepAxis(
    name="light_source_jitter",
    note="small light position changes reveal whether the scene is robust or only works from one lucky angle",
    values=(
        ("locked", {"light_jitter_radius": 0.0, "light_jitter_count": 1, "light_energy_variance": 0.0}),
        ("handheld", {"light_jitter_radius": 0.18, "light_jitter_count": 3, "light_energy_variance": 0.08}),
        ("restless", {"light_jitter_radius": 0.42, "light_jitter_count": 5, "light_energy_variance": 0.18}),
    ),
)

LIGHT_SOURCE_SIZE = SweepAxis(
    name="light_source_size",
    note="light size controls hard graphic shadows versus broad photographic wrap",
    values=(
        ("pin", {"key_light_size": 0.08, "key_light_energy": 420}),
        ("softbox", {"key_light_size": 2.4, "key_light_energy": 520}),
        ("sky_panel", {"key_light_size": 6.5, "key_light_energy": 740}),
    ),
)

TEXTURE_MAGNITUDE = SweepAxis(
    name="texture_magnitude",
    note="texture magnitude should be swept separately from color so form does not get buried",
    values=(
        ("clean", {"texture_magnitude": 0.0, "noise_strength": 0.0, "surface_bump_strength": 0.0}),
        ("marked", {"texture_magnitude": 0.45, "noise_strength": 0.42, "surface_bump_strength": 0.08}),
        ("craggy", {"texture_magnitude": 1.1, "noise_strength": 0.95, "surface_bump_strength": 0.24}),
    ),
)

TEXTURE_SCALE = SweepAxis(
    name="texture_scale",
    note="cross texture scale with magnitude to avoid mistaking frequency for strength",
    values=(
        ("fine", {"noise_scale": 80.0, "texture_scale": 0.22}),
        ("medium", {"noise_scale": 16.0, "texture_scale": 1.0}),
        ("broad", {"noise_scale": 3.2, "texture_scale": 3.4}),
    ),
)

TEXTURE_MAGNITUDE_STRIDE = stride_axis(
    "texture_magnitude_stride",
    "texture_magnitude",
    center=0.55,
    stride=0.35,
    steps=(-2, -1, 0, 1, 2),
    clamp_min=0.0,
    note="increase stride when clean/grain/rugged looks too timid",
)

GLOW_BLOOM = SweepAxis(
    name="glow_bloom",
    note="bloom and halo sweeps are best kept small because too much glow erases structure",
    values=(
        ("dry", {"glow_radius": 0.0, "glow_strength": 0.0, "halo_alpha": 0.0}),
        ("rim", {"glow_radius": 0.45, "glow_strength": 0.28, "halo_alpha": 0.08}),
        ("washed", {"glow_radius": 1.2, "glow_strength": 0.72, "halo_alpha": 0.22}),
    ),
)

CAMERA_JITTER = SweepAxis(
    name="camera_jitter",
    note="camera jitter tests whether composition survives small framing accidents",
    values=(
        ("tripod", {"camera_jitter": 0.0, "camera_roll_jitter": 0.0}),
        ("breathing", {"camera_jitter": 0.035, "camera_roll_jitter": 0.4}),
        ("loose", {"camera_jitter": 0.09, "camera_roll_jitter": 1.2}),
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
        LIGHT_SOURCE_JITTER,
        LIGHT_SOURCE_SIZE,
        TEXTURE_MAGNITUDE,
        TEXTURE_SCALE,
        TEXTURE_MAGNITUDE_STRIDE,
        GLOW_BLOOM,
        CAMERA_JITTER,
        SILHOUETTE_SHAPE,
    ]
}

TILE_PRESETS = {
    "hero_pair": TileSpec.hero_pair(),
    "balanced_grid": TileSpec.balanced_grid(),
    "micro_grid": TileSpec.micro_grid(),
    "auto_micro_grid": TileSpec.auto_micro_grid(),
    "tiny_grid": TileSpec.tiny_grid(),
    "auto_tiny_grid": TileSpec.auto_tiny_grid(),
    "square_moodboard": TileSpec.square_moodboard(),
    "auto_square_moodboard": TileSpec.auto_square_moodboard(),
    "filmstrip": TileSpec.filmstrip(),
}

RENDER_PRESETS = {
    "shape_scout": RenderConfig.shape_scout(),
    "material_scout": RenderConfig.material_scout(),
    "cycles_preview": RenderConfig.cycles_preview(),
    "hero_check": RenderConfig.hero_check(),
}
