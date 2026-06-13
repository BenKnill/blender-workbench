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

Run a density-texture-focused scout:

```bash
/Applications/Blender.app/Contents/MacOS/Blender --background --python examples/rocket_plume_texture_scout.py
```

This dense sheet uses smooth, overdone, and whiteout anchors so texture stride is easy to widen or narrow. In this recipe, plume texture means spatial density structure: translucent ribbons, wispy strands, clumps, and turbulence distributed through the plume volume. Shader noise is secondary. The overdone region is often the most aesthetically interesting; whiteout is the actual failure anchor.

![Rocket plume texture scout contact sheet](assets/rocket-plume-texture-scout.jpg)

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
    resolution_x=560,
    resolution_y=360,
    samples=16,
    camera_name=ROCKET_PLUME_CAMERA,
    tile=TILE_PRESETS["auto_tiny_grid"],
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
- `density_ribbon_count`, `density_wisp_count`, and `density_clump_count`: spatial density texture.
- `density_ribbon_width`, `density_wisp_radius`, and `density_clump_scale`: size of texture structures.
- `filament_wiggle`: turbulence in strand paths.
- `plume_texture_magnitude` and `billow_texture_magnitude`: secondary shader-noise texture, not the main density structure.
- `warmth`: tiny color contamination. Keep this low unless deliberately testing failure.

## Performance Notes

Start with `cycles_preview` at 24 to 32 samples. The recipe uses cheap geometry: open cones, curve filaments, and low-poly ellipsoid billows. If a sheet becomes slow, reduce `filament_count`, `billow_count`, tile count, or postprocessing before reducing the clarity of the sweep.

On the current Mac/Blender 5.1 run, the dense texture scout rendered 16 tiny tiles in about 32.5 seconds at 560x360 and 16 Cycles samples. The 9-tile alpha/shape scout with default density texture rendered in about 21 seconds at 640x420 and 24 samples.

Use the dense texture scout to set stride before paying for the full alpha/shape sheet. Use `hero_check` only after the smaller sheets have chosen a shape, alpha regime, and texture range.
