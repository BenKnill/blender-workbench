# Blender Workbench

Reusable helpers for Blender visual experiments where the goal is not one lucky render, but a traceable parameter sweep with contact-sheet tiles and metadata.

This repo grew out of the lighting/plume studies in the neighboring Blender scene lab. The main lesson: agents should not hand-roll a new sweep harness every time. Define a parameter object, write one scene builder, render a matrix, inspect the tiles, then promote the best setting back into the scene.

## What This Provides

- `blender_workbench.sweep`: render a list/grid of variants, write raw/finished PNGs, metadata, README, and a contact sheet.
- `blender_workbench.materials`: small material helpers with explicit alpha semantics.
- `blender_workbench.presets`: starter axes and tile layouts for common visual experiments.
- `examples/mini_plume_sweep.py`: a compact Blender script showing the intended workflow.
- `docs/parameter-sweep-pattern.md`: the short operating pattern for future agents.

## Quick Start

Run an example through Blender:

```bash
/Applications/Blender.app/Contents/MacOS/Blender --background --python examples/mini_plume_sweep.py
```

The example writes to `examples/output/mini_plume_sweep/`.

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
from blender_workbench.presets import SWEEP_AXES, TILE_PRESETS, one_axis_variants, two_axis_variants
from blender_workbench.sweep import RenderConfig, render_sweep

variants = two_axis_variants(
    SWEEP_AXES["plume_alpha_strength"],
    SWEEP_AXES["plume_shape"],
    base={"samples": 48},
)

render_sweep(
    variants=variants,
    build_scene=build_scene,
    out_dir=OUT,
    config=RenderConfig(tile=TILE_PRESETS["micro_grid"]),
)
```

Use `micro_grid` when you need lots of little tiles, `hero_pair` for before/after comparisons, `balanced_grid` for readable 3x3 studies, `square_moodboard` for palette and shape boards, and `filmstrip` for temporal or ordered sweeps.
