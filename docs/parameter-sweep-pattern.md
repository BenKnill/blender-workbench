# Parameter Sweep Pattern

Use this repo when a Blender idea needs fast visual comparison instead of one-off scene scripts.

## Agent Loop

1. Write a settings object or dict with the smallest meaningful knobs.
2. Write one `build_scene(settings)` function that fully rebuilds the scene.
3. Render a low-cost sweep with fixed camera, resolution, and samples.
4. Read the contact sheet before changing the scene.
5. Promote the best settings into a named preset.
6. Render one heavier version only after the sweep explains the direction.

## Sweep Design

Good sweep axes are visual and isolated:

- alpha versus emission strength
- plume width versus plume length
- scattering radius versus density
- sunset color temperature versus haze amount
- caustic scale versus water roughness
- subsurface color versus radius

Avoid mixing too many axes in one grid. A 2x3 or 3x3 sheet is often more useful than a huge matrix because the eye can still compare cause and effect.

## Contact Sheet Rules

- Keep the camera locked unless framing is the parameter under test.
- Include at least one failure anchor when the failure mode is informative.
- Put generated images under ignored output folders such as `examples/output/` or `runs/`.
- Keep `metadata.json` next to the tiles so visual picks can become reproducible presets.
- Prefer small diagnostic renders, then spend samples on the winner.

## Transparency Lesson

For transparent emission materials, `alpha=0` must mean fully transparent and `alpha=1` must mean fully emissive. This was easy to invert during the vacuum plume work, and an inverted mix makes sweeps misleading because "more alpha" visually does less.

Use `blender_workbench.materials.transparent_emission_material` for this pattern unless a scene has a strong reason to build its own shader.
