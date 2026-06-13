# Blender Workbench Agent Guide

This repo exists to steer Blender agents toward reusable parameter-sweep functionality.

When making or modifying a Blender experiment:

- Prefer `blender_workbench.sweep.render_sweep` over bespoke loops.
- Check `blender_workbench.presets.SWEEP_AXES` and `TILE_PRESETS` before inventing new parameters or contact-sheet layouts.
- Always keep numeric settings in metadata next to rendered tiles.
- Render small diagnostic sweeps before hero renders.
- Keep the camera fixed inside a sweep unless camera/framing is the parameter being tested.
- Use `label`/`note` fields so a contact sheet has an interpretable reading order.
- If alpha/transparency matters, use `blender_workbench.materials.transparent_emission_material`; `alpha=0` means fully transparent, `alpha=1` means fully emissive.
- Include a deliberate failure anchor when useful, such as "too opaque" or "wrong torch", so the visual scale is calibrated.
- After a sweep, promote the chosen settings into a named constant in the scene script.
- Open promising `.blend` files in Blender GUI for an eyeball pass before declaring victory.

Good default sweep directions:

- shape first: silhouette, scale, taper, bend, density
- material second: alpha, roughness, subsurface radius, emission strength
- lighting third: key color, horizon color, haze density, caustic scale
- composition last: camera height, focal length, crop, background contrast

Do not let generated artifacts drown the repo. Put sweep outputs under `examples/output/`, `runs/`, or another ignored directory.
