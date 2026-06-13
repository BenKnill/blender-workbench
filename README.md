# Blender Workbench

Reusable helpers for Blender visual experiments where the goal is not one lucky render, but a traceable parameter sweep with contact-sheet tiles and metadata.

This repo grew out of the lighting/plume studies in the neighboring Blender scene lab. The main lesson: agents should not hand-roll a new sweep harness every time. Define a parameter object, write one scene builder, render a matrix, inspect the tiles, then promote the best setting back into the scene.

## What This Provides

- `blender_workbench.sweep`: render a list/grid of variants, write raw/finished PNGs, metadata, README, and a contact sheet.
- `blender_workbench.materials`: small material helpers with explicit alpha semantics.
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
