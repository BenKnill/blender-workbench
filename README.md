# Blender Workbench

Reusable helpers for Blender visual experiments where the goal is not one lucky render, but a traceable parameter sweep with contact-sheet tiles and metadata.

This repo grew out of the lighting/plume studies in the neighboring Blender scene lab. The main lesson: agents should not hand-roll a new sweep harness every time. Define a parameter object, write one scene builder, render a matrix, inspect the tiles, then promote the best setting back into the scene.

## What This Provides

- `blender_workbench.sweep`: render a list/grid of variants, write raw/finished PNGs, metadata, README, and a contact sheet.
- `blender_workbench.materials`: small material helpers with explicit alpha semantics.
- `blender_workbench.presets`: starter axes, render profiles, and tile layouts for common visual experiments.
- `blender_workbench.recipes`: optional domain recipes, including a fast rocket vacuum plume scout.
- `examples/mini_plume_sweep.py`: a compact Blender script showing the intended workflow.
- `examples/light_texture_scout.py`: named light-jitter and texture-magnitude board.
- `examples/rocket_plume_scout.py`: a stronger plume use case built on the general sweep API.
- `examples/rocket_plume_texture_scout.py`: plume texture stride scout from smooth to overdone.
- `docs/parameter-sweep-pattern.md`: the short operating pattern for future agents.
- `docs/performance.md`: defaults for fast basics-first exploration.
- `docs/rocket-plume.md`: recipe notes for broad, smoky, in-space engine plumes.

## Quick Start

Run an example through Blender:

```bash
/Applications/Blender.app/Contents/MacOS/Blender --background --python examples/mini_plume_sweep.py
```

The example writes to `examples/output/mini_plume_sweep/`.

![Mini plume sweep contact sheet](docs/assets/mini-plume-sweep.jpg)

## Agent Loop

1. Define a small dataclass or dict of meaningful parameters.
2. Write `build_scene(settings)` so it constructs the entire scene from those parameters.
3. Use `render_sweep(...)` with one fixed camera first.
4. Inspect `contact_sheet.png`.
5. Widen or narrow the sweep based on what the sheet shows.
6. Promote a chosen setting into the main scene only after seeing the grid.

## Design Bias

Prefer fast diagnostic sweeps before expensive hero bakes. A good sweep makes failure modes visible: too opaque, too noisy, too flat, wrong color, bad framing, over-bloomed, under-structured.

Generated renders belong in ignored output directories, not the repo history.

## Starter Defaults

Useful imports for new experiments:

```python
from dataclasses import replace

from blender_workbench.presets import RENDER_PRESETS, SWEEP_AXES, TILE_PRESETS, stride_axis, two_axis_variants
from blender_workbench.sweep import named_variants, render_sweep

variants = two_axis_variants(
    SWEEP_AXES["plume_alpha_strength"],
    SWEEP_AXES["plume_shape"],
    base={"samples": 48},
)

render_sweep(
    variants=variants,
    build_scene=build_scene,
    out_dir=OUT,
    config=replace(RENDER_PRESETS["cycles_preview"], tile=TILE_PRESETS["micro_grid"]),
)
```

Use `micro_grid` when you need lots of little tiles, `auto_micro_grid` or `square=True` when the sheet should choose near-square columns, `hero_pair` for before/after comparisons, `balanced_grid` for readable 3x3 studies, `square_moodboard` for palette and shape boards, and `filmstrip` for temporal or ordered sweeps.

Use `shape_scout` for silhouette/form, `material_scout` for quick color and transparency reads, `cycles_preview` when lighting matters, and `hero_check` only after a smaller sheet has picked a direction.

For named moodboards, skip row/column ceremony:

```python
variants = named_variants(
    {
        "clean": {"texture_magnitude": 0.0},
        "marked": {"texture_magnitude": 0.45, "noise_scale": 80.0},
        "craggy": {"texture_magnitude": 1.1, "noise_scale": 16.0},
        "overdone_fail": {"texture_magnitude": 1.9, "noise_scale": 28.0},
    }
)

render_sweep(
    variants=variants,
    build_scene=build_scene,
    out_dir=OUT,
    config=replace(RENDER_PRESETS["material_scout"], tile=TILE_PRESETS["auto_micro_grid"]),
    square=True,
)
```

Good current axes include `light_source_jitter`, `light_source_size`, `texture_magnitude`, `texture_scale`, `glow_bloom`, and `camera_jitter`.

For fast stride adjustment, build an axis around a center value:

```python
texture_stride = stride_axis(
    "texture_stride",
    "texture_magnitude",
    center=0.55,
    stride=0.35,
    clamp_min=0.0,
)
```

If the sheet is too subtle, double `stride`; if every tile is chaos, halve it.

![Light texture scout contact sheet](docs/assets/light-texture-scout.jpg)

## Featured Recipe: Rocket Plume

Run the stronger plume scout:

```bash
/Applications/Blender.app/Contents/MacOS/Blender --background --python examples/rocket_plume_scout.py
```

This uses `blender_workbench.recipes.rocket_plume` to cross plume alpha/strength with broad vacuum expansion shape. It is a demanding recipe, but the workbench should remain a general sweep tool rather than a rocket-only optimizer.

![Rocket plume scout contact sheet](docs/assets/rocket-plume-scout.jpg)

Run the plume texture scout:

```bash
/Applications/Blender.app/Contents/MacOS/Blender --background --python examples/rocket_plume_texture_scout.py
```

![Rocket plume texture scout contact sheet](docs/assets/rocket-plume-texture-scout.jpg)
