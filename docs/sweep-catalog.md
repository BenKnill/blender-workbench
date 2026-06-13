# Sweep Catalog

This is a starter menu for fast Blender exploration. Use it to choose a sweep shape before writing a scene.

Start with the cheapest render profile that can answer the visual question. Shape questions usually belong in `shape_scout`; material questions in `material_scout`; lighting questions in `cycles_preview`.

## Tile Layouts

- default `TileSpec`: tiny square tiles with near-square columns chosen from the variant count.
- `hero_pair`: two larger square tiles for before/after, winner/failure, reference/attempt.
- `balanced_grid`: readable small square sheets for causal sweeps.
- `micro_grid`: many little square tiles for broad scouting, color palettes, noisy alpha tests, and silhouette thumbnails.
- `auto_micro_grid`: little square tiles with near-square columns chosen from the variant count.
- `tiny_grid`: even smaller square tiles for dense boards.
- `auto_tiny_grid`: dense boards with near-square columns chosen from the variant count.
- `square_moodboard`: compact square tiles for shape boards, material chips, and palette studies.
- `auto_square_moodboard`: named case boards without pre-deciding the row count.
- `filmstrip`: ordered tiles for motion, time-of-day, long-exposure streak length, or camera path tests.

For named cases, prefer `named_variants(...)` plus `render_sweep(..., square=True)`. Use row/column axes only when the comparison really is a crossed parameter grid.

For numeric parameters, use `stride_axis(...)` when you expect to adjust the sweep width repeatedly. If the resulting sheet looks timid, increase `stride`; if every tile fails, reduce it.

For recipe-specific stride boards, prefer named stride kwargs such as `lens_stride`, `ior_stride`, or `thickness_stride`. A 5x5 sheet works well when each row isolates one variable and each column is the same `m2, m1, base, p1, p2` step pattern.

## Shape Sweeps

- silhouette: spindly, blocky, swept, squat, tall
- taper: cylinder, cone, bell, horn, fan
- density: sparse filaments, medium ribs, packed threads
- deformation: straight, bowed, twisted, turbulent
- scale: tiny detail, readable mid-form, huge framing shape

Shape sweeps should usually happen before material polish. If the thumbnail is not readable, the shader will not rescue it.

## Material Sweeps

- transparent emission: alpha crossed with strength
- transparent glass: alpha, transmission, roughness, IOR, tint, pane thickness
- smoke: density crossed with anisotropy
- glass or water: roughness crossed with caustic scale
- subsurface: radius crossed with color
- metal: roughness crossed with edge light strength
- texture magnitude: clean, marked, craggy, overdone
- texture scale: fine, medium, broad

Keep one deliberate failure anchor in material sheets. It calibrates the eye and makes the good tile more legible.

## Color And Light Sweeps

- light source jitter: locked, handheld, restless
- light source size: pin, softbox, sky panel
- sunset haze: sky color, horizon color, haze density
- moonrise trail: streak warmth, halo radius, sky exposure
- glow bloom: dry, rim, washed
- camera jitter: tripod, breathing, loose
- camera perspective: wide/close, normal/mid, portrait/far, tele/flat
- camera orbit: front low, left/right mid, high three-quarter
- caustics: light size, water roughness, pattern scale
- space plume: blue-white emission, soft gray shell, low fire color
- subsurface candy: opal, amber, ruby, sea-glass

Color sweeps should avoid one-note palettes. Put at least one cool/warm contrast or neutral anchor in the grid.

## Good First Sheets

- `plume_alpha_strength` x `plume_shape` with `micro_grid`
- named texture cases with `auto_square_moodboard` and `square=True`
- `examples/camera_perspective_scout.py` for a 5x5 lens/yaw/pitch/roll/depth stride sheet
- `examples/gobo_lighting_scout.py` for projected shadow texture, gel color, and light softness
- `examples/subsurface_scout.py` for translucent wax/jelly/opal material reads with thickness and backlight
- `examples/transparency_scout.py` for a 5x5 alpha/roughness/IOR/thickness/tint stride sheet
- `examples/light_texture_scout.py` for a concrete named light-jitter plus texture-magnitude board
- `examples/rocket_plume_texture_scout.py` for a dense plume density-texture board from smooth through overdone to whiteout
- `light_source_jitter` x `texture_magnitude` with `balanced_grid`
- `sunset_haze` as a one-axis `filmstrip`
- `subsurface_candy` x shape scale with `square_moodboard`
- caustic water scale x roughness with `balanced_grid`
- silhouette shape as unlabeled micro thumbnails, then rerun winners with labels
