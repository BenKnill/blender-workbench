# Parameter Sweep Pattern

Use this repo when a Blender idea needs fast visual comparison instead of one-off scene scripts.

## Agent Loop

1. Write a settings object or dict with the smallest meaningful knobs.
2. Write one `build_scene(settings)` function that fully rebuilds the scene.
3. Render a low-cost sweep with fixed camera, resolution, and samples.
4. Read the contact sheet before changing the scene.
5. Pick the best tile by exact variant name or 1-based index.
6. Render that pick with `render_selected_from_sweep(...)`.
7. Save a `.blend` for GUI inspection when the viewport would reveal setup, camera, material, or light-placement mistakes faster than another PNG.
8. Promote the selected settings into a named preset only after the heavier render or GUI handoff still works.

## Sweep Design

Good sweep axes are visual and isolated:

- alpha versus emission strength
- plume width versus plume length
- scattering radius versus density
- sunset color temperature versus haze amount
- caustic scale versus water roughness
- subsurface color versus radius

Avoid mixing too many axes in one grid. A 2x3 or 3x3 sheet is often more useful than a huge matrix because the eye can still compare cause and effect.

## Example Preflight

Before refreshing docs assets or running a dependent example, check the manifest:

```bash
python3 tools/example_preflight.py
python3 tools/example_preflight.py --ready-only --max-cost quick --sort-by-cost
```

Each manifest entry records the example command, expected output files, docs asset, generated-input prerequisites, and cost metadata. If a dependency is missing, the preflight report prints the upstream command to create it instead of letting the example fail later with a bare `FileNotFoundError`. Use `--max-cost quick` when the next useful move should be a cheap scout rather than a medium or heavy render session.

## Contact Sheet Rules

- Keep the camera locked unless framing is the parameter under test.
- Include at least one explicit `failure_anchor` role when the failure mode is informative.
- Use `baseline` for neutral/reference tiles, `candidate` for normal sweep choices, `aesthetic_extreme` for useful overdone edges, and `negative_control` when the tile is deliberately wrong.
- Put generated images under ignored output folders such as `examples/output/` or `runs/`.
- Keep `metadata.json` next to the tiles so visual picks can become reproducible presets.
- Prefer small diagnostic renders, then spend samples on the winner with `RENDER_PRESETS["hero_check"]`.

## Selection Render

After a sheet renders, choose one tile and render it larger:

```python
from blender_workbench.presets import RENDER_PRESETS
from blender_workbench.sweep import render_selected_from_sweep

render_selected_from_sweep(
    sweep_dir=OUT,
    pick="mesh_fill_p1",
    build_scene=build_scene,
    config=RENDER_PRESETS["hero_check"],
    save_blend=True,
)
```

The selected render writes `selected.json`, preserving the pick, settings, render config, source sweep, final file paths, and any exported `.blend` path plus an `open -a Blender ...` command. Pass `render_image=False` with `save_blend=True`, or use an example's `--export-blend-only`, for a fast viewport handoff without a selected PNG.

## Pick Smoke Checks

When an example exposes `--pick`, prove the promotion path with a tiny selected render before opening a PR:

```bash
python3 tools/example_pick_smoke.py --name soft_atmosphere_scout
python3 tools/example_pick_smoke.py --name soft_atmosphere_scout --run --hero-samples 4
```

The smoke helper chooses a real variant from existing `metadata.json`, runs the example's `--pick` path through Blender only when `--run` is passed, then checks `selected.json`, source sweep provenance, and output files.

## Postprocess Sweep

When the scene is already selected, reuse one raw render for finishing looks:

```python
from blender_workbench.postprocess import postprocess_look_variants, render_postprocess_sweep

render_postprocess_sweep(
    raw_image=OUT / "selected" / "terrain_relief_p2" / "terrain_relief_p2.hero.raw.png",
    variants=postprocess_look_variants(),
    out_dir=OUT / "looks",
    root=ROOT,
)
```

Use this for glow, contrast, saturation, warm/cool grade, vignette, and similar compositor/look decisions. The metadata records the source raw image and look settings for each tile.

## Metadata-Driven Promotion

If the visual decision happens later from `contact_sheet.png` and `metadata.json`, promote the existing tile without reconstructing the original variant list:

```bash
PYTHONPATH=src /Applications/Blender.app/Contents/MacOS/Blender --background --python-expr \
'import blender_workbench.promote as p; p.main(["--sweep", "examples/output/mesh_light_scout", "--pick", "mesh_fill_p1", "--recipe", "blender_workbench.recipes.mesh_light:build_mesh_light_scene", "--camera-name", "mesh_light_camera", "--save-blend"])'
```

The `--pick` value accepts the same 1-based index, exact variant name, or exact label as `render_selected_from_sweep(...)`. The command writes `selected/<pick>/selected.json` with source sweep provenance and the recovered settings from metadata.

This metadata-based path is preferred because the selected render is rebuilt from the sweep artifact the agent actually inspected. If the script already has the same variant list in memory, `render_selected_variant(...)` is still available.

## Transparency Lesson

For transparent emission materials, `alpha=0` must mean fully transparent and `alpha=1` must mean fully emissive. This was easy to invert during the vacuum plume work, and an inverted mix makes sweeps misleading because "more alpha" visually does less.

Use `blender_workbench.materials.transparent_emission_material` for this pattern unless a scene has a strong reason to build its own shader.
