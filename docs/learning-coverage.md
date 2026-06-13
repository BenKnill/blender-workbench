# Learning Coverage Map

This map answers what happened after a learning/resource prompt became useful: implemented scout, linked issue, generated artifact, deliberate skip, or stale follow-up. The machine-readable ledger is `docs/learning-coverage.json`; this page is the human table.

Run the checker before filing duplicate scout work:

```bash
python3 tools/learning_coverage.py report --fail-uncovered
```

When a source prompt becomes a new scout, docs page, issue, local reference study, or deliberate skip, update `docs/learning-coverage.json` in the same change.

| Coverage row | Source prompt | Status | Implemented scouts | Issue links | Artifact/docs cues |
| --- | --- | --- | --- | --- | --- |
| `blenderart27-cg-lighting-packshot` | BlenderArt issue 27 CG lighting, shadow play, mesh lights, pack-shot camera controls | `implemented` | `examples/gobo_lighting_scout.py`, `examples/mesh_light_scout.py`, `examples/metal_edge_light_scout.py`, `examples/camera_perspective_scout.py` | #15, #17 | `docs/assets/gobo-lighting-scout.jpg`, `docs/assets/mesh-light-scout.jpg`, `docs/assets/metal-edge-light-scout.svg` |
| `blenderart16-material-transparency-smoke` | BlenderArt issue 16 SSS, translucent/transparent materials, smoke and alpha billboards | `issue_open` | `examples/layered_material_scout.py`, `examples/subsurface_scout.py`, `examples/transparency_scout.py`, `examples/soft_atmosphere_scout.py` | #14, #16, #23 | `docs/assets/layered-material-scout.svg`, `docs/assets/subsurface-scout.jpg`, `docs/assets/transparency-scout.jpg` |
| `blenderart22-texture-environment-node-prompts` | BlenderArt issue 22 texture nodes, environment lighting, trial-and-error material lighting | `issue_open` | `examples/procedural_texture_scout.py`, `examples/light_texture_scout.py`, `examples/terrain_environment_scout.py` | #12, #22 | `docs/assets/procedural-texture-scout.svg`, `docs/source-translation.md` |
| `blenderart39-virtual-landscape-compositing` | BlenderArt issue 39 virtual sets, landscapes, render passes, compositing | `issue_open` | `examples/terrain_environment_scout.py`, `examples/render_pass_diagnostic_scout.py`, `examples/postprocess_look_scout.py`, `examples/camera_perspective_scout.py` | #21, #24, #28, #32 | `docs/assets/render-pass-diagnostic-scout.svg`, `docs/assets/postprocess-look-scout.jpg` |
| `blenderart42-diffuser-hard-surface-material` | BlenderArt issue 42 diffuser light objects and mixed hard-surface/organic material workflows | `issue_open` | `examples/metal_edge_light_scout.py` | #14, #17, #23, #32 | `docs/assets/metal-edge-light-scout.svg`, `docs/source-translation-ledger.json` |
| `spacex-plume-frame-references` | SpaceX plume reference frames and adjacent vacuum plume studies | `implemented` | `examples/mini_plume_sweep.py`, `examples/rocket_plume_scout.py`, `examples/rocket_plume_texture_scout.py` | - | `docs/rocket-plume.md`, `docs/assets/rocket-plume-texture-scout.jpg` |
| `fast-lighting-study-reference-prompts` | Local fast distinct lighting studies and `reference_use_prompt.md` handoff constraints | `issue_open` | - | #32, #40, #42 | `../fast_distinct_lighting_studies_v2/*/reference_use_prompt.md` |
| `fast-knight-study-reference-prompts` | Local fast knight pose/bind studies and structure-preservation prompts | `issue_open` | - | #29, #40 | `../fast_distinct_knight_studies/*/reference_use_prompt.md` |

Coverage is intentionally about the learning pipeline, not PDF extraction. Use `tools/pdf_lesson_index.py` and `tools/pdf_triage.py` to inspect source ranges; use this map to record what the workbench did with the prompt afterward.
