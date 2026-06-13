# Learning Notes

This is a compact map from the local BlenderArt/resource shelf to workbench exercises.

## Current Source Prompts

- `blenderart_issue_27_cg_lighting_apr_2010.pdf`: textured light, shadow play, mesh/glowing lights, pack-shot camera controls, zoom/focal blur, studio tables.
- `blenderart_issue_16_lighting_rendering_may_2008.pdf`: multilayer skin/SSS thinking, translucent-vs-transparent materials, smoke and alpha billboards.
- `blenderart_issue_22_texturing_environment_lighting_jun_2009.pdf`: texture-node thinking, candle/face SSS, trial-and-error material lighting.
- `blenderart_issue_39_compositing_sep_2012.pdf`: virtual sets that survive multiple camera setups, displacement landscapes, SSS ice, render passes/compositing.
- `blenderart_issue_42_general_inspiration_sep_2013.pdf`: translucent printed china-ball lighting objects and mixed hard-surface/organic material workflows.

## Recipes Added From These Prompts

- `examples/gobo_lighting_scout.py`: turns textured light and shadow-play notes into a 16-tile projected-shadow board.
- `examples/mesh_light_scout.py`: turns mesh-light and studio softbox notes into a same-view emissive size, distance, height, fill, and gel/shape board.
- `examples/subsurface_scout.py`: turns SSS/translucency notes into wax, jelly, opal, thickness, backlight, and core-light comparisons.
- `examples/terrain_environment_scout.py`: turns issue 39 landscape/Europa and virtual-environment prompts into same-view relief, strata, haze, backlight, and foreground-scale comparisons.
- `examples/postprocess_look_scout.py`: turns issue 39 compositing/finishing prompts into a one-source glow, contrast, saturation, warmth, and vignette sheet.
- `examples/camera_perspective_scout.py`: turns pack-shot and virtual-set camera lessons into same-view lens and scene-depth-cue sweeps.
- `examples/transparency_scout.py`: turns alpha/glass/refraction notes into alpha, transmission, roughness, IOR, tint, and pane-thickness comparisons.

## Workbench Lessons

- Do not use the default glow postprocess for every recipe. It helps plumes, but it can obscure material, shadow, and camera diagnostics.
- Tiny boards need short labels or adaptive label sizing. Long descriptive variant names belong in metadata, not necessarily on the tile.
- Perspective is a first-class variable. Pair lens and distance when you want similar composition with different spatial feeling.
- Yaw and roll usually change the shot instead of tuning the scene. For parameter smelling, keep the view steady and alter foreground, background, grid, and subject depth cues.
- Transparent materials need structured backgrounds. Without stripes/checkers/depth markers, alpha and IOR sweeps look deceptively identical.
- Same-y boards usually mean the stride is too small. Use 5x5 stride sheets with one variable per row before adding more hand-picked named cases.
- Visible light geometry is a useful diagnostic object, not only a renderer feature. Mesh-light boards should show both illumination on the subject and the light source's shape/gel behavior when possible.
- Environment boards need foreground, midground, and horizon diagnostics in the same tile. Terrain relief alone is too abstract unless haze, strata, and silhouette scale are visible together.
- Selected renders are better at exposing hard card edges than tiny contact sheets. Use reusable feathered primitives for horizon glow, haze sheets, and stylized light cards.
- Compositing choices deserve their own sweep surface. Reusing one raw render for look variants is much cheaper than rerendering the scene for every glow or color-grade idea.
