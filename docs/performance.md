# Performance Guide

The workbench should make the first useful sheet cheap. Spend time on wide visual search, then spend samples on winners.

## Render Profiles

- `shape_scout`: Workbench engine, 520x340, one sample, micro tiles. Use for silhouette, scale, layout, density, and camera blocking.
- `material_scout`: Eevee when available, 640x420, low samples, micro tiles. Use for color, alpha, transparency, roughness, and broad material direction.
- `cycles_preview`: Cycles, 760x500, 32 samples, reduced bounces. Use when glow, lighting, glass, subsurface, or volumetrics matter.
- `hero_check`: Cycles, 1280x840, 96 samples. Use only after a smaller sweep has shortlisted settings.

Use `dataclasses.replace(...)` to make local tweaks without losing the preset name:

```python
from dataclasses import replace

from blender_workbench.presets import RENDER_PRESETS, TILE_PRESETS

config = replace(
    RENDER_PRESETS["cycles_preview"],
    camera_name="camera_profile",
    tile=TILE_PRESETS["micro_grid"],
)
```

## Fast Exploration Rules

- Keep early sheets between 6 and 24 tiles; 25 is fine for a structured 5x5 stride board.
- Prefer `micro_grid` for broad scouting and `balanced_grid` for readable 3x3 comparisons.
- Turn postprocessing off when testing shape or framing: `render_sweep(..., postprocess=None)`.
- Reuse tiles during layout churn with `replace(config, reuse_existing=True)`.
- Keep camera perspective scouts cheap: the variable is usually lens or scene depth cues, not samples.
- Keep `build_scene(settings)` cheap: avoid simulations, huge mesh generation, high subdivision, and expensive boolean stacks in the first pass.
- Add detail in stages: silhouette, material, lighting, camera, then heavier bake.
- When a numeric sweep looks timid, increase the `stride_axis(...)` stride and rerun. When every tile fails, reduce the stride or add failure anchors at the extremes.
- When a whole recipe looks timid, prefer widening its stride kwargs over adding more hand-named cases.

## Reading Timing Metadata

Each `metadata.json` records:

- `render_config`: the engine, resolution, sample count, tile preset, and cache behavior.
- `total_seconds`: elapsed time for the sweep.
- per-variant `build_seconds`, `render_seconds`, `postprocess_seconds`, and `skipped_existing`.

If `build_seconds` is high, simplify geometry or precompute shared assets. If `render_seconds` is high, reduce samples, resolution, bounces, volumetrics, or tile count. If `postprocess_seconds` is high, disable glow/contrast until the sheet is narrowed.

For stacked transparent materials, watch `transparent_max_bounces`. Too low can create dark termination artifacts; too high can slow dense sheets. Rocket plume previews default higher than ordinary previews because they layer shells, billows, and filaments.

## Useful Ladders

- Shape: `shape_scout` + `micro_grid`, then rerun winners with `cycles_preview`.
- Camera: `cycles_preview` with low samples if shadows/markers matter; otherwise `shape_scout` is enough for framing.
- Transparency: `material_scout` first, then `cycles_preview` if alpha sorting or glow is misleading.
- Caustics: start with `cycles_preview`, keep the grid small, then use `hero_check` only for the final two or three variants.
- Long exposure: scout streak length and framing with `shape_scout`, then test glow and haze with `cycles_preview`.
