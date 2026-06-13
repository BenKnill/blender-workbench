# Rocket Plume Recipe

The workbench should stay general, but rocket plumes are a useful stress test because they need shape, transparency, glow, scale, and failure anchors in one sheet.

Use `blender_workbench.recipes.rocket_plume` when scouting an upper-stage or in-space engine plume.

## Visual Target

The default recipe aims for:

- broad translucent expansion rather than a narrow torch
- blue-white filaments and a gray-blue shell rather than saturated orange fire
- a short bright engine core, not a long flame
- soft billowy structure that reads at thumbnail size
- deterministic procedural variation so parameter changes can be compared fairly

## First Scout

```bash
/Applications/Blender.app/Contents/MacOS/Blender --background --python examples/rocket_plume_scout.py
```

The example writes a 3x3 contact sheet to `examples/output/rocket_plume_scout/`.

![Rocket plume scout contact sheet](assets/rocket-plume-scout.jpg)

## Recipe API

```python
from dataclasses import replace

from blender_workbench.presets import RENDER_PRESETS, TILE_PRESETS
from blender_workbench.recipes.rocket_plume import (
    ROCKET_PLUME_CAMERA,
    build_rocket_plume_scene,
    rocket_plume_scout_variants,
)
from blender_workbench.sweep import render_sweep

config = replace(
    RENDER_PRESETS["cycles_preview"],
    samples=24,
    camera_name=ROCKET_PLUME_CAMERA,
    tile=TILE_PRESETS["micro_grid"],
)

render_sweep(
    variants=rocket_plume_scout_variants(),
    build_scene=build_rocket_plume_scene,
    out_dir=OUT,
    config=config,
    square=True,
)
```

## Parameters Worth Sweeping

- `shell_alpha` and `shell_strength`: the main anti-torch controls.
- `width` and `length`: vacuum expansion shape.
- `filament_count`, `filament_alpha`, and `filament_strength`: edge structure.
- `smoke_alpha`, `smoke_strength`, and `billow_count`: broad cloudy read.
- `warmth`: tiny color contamination. Keep this low unless deliberately testing failure.

## Performance Notes

Start with `cycles_preview` at 24 to 32 samples. The recipe uses cheap geometry: open cones, curve filaments, and low-poly ellipsoid billows. If a sheet becomes slow, reduce `filament_count`, `billow_count`, tile count, or postprocessing before reducing the clarity of the sweep.

On the initial Mac/Blender 5.1 run, the 9-tile scout rendered in about 15 seconds at 640x420 and 24 Cycles samples.

Use `hero_check` only after the 3x3 sheet has chosen a shape and alpha regime.
