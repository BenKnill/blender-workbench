# Sweep Catalog

This is a starter menu for fast Blender exploration. Use it to choose a sweep shape before writing a scene.

## Tile Layouts

- `hero_pair`: two large tiles for before/after, winner/failure, reference/attempt.
- `balanced_grid`: readable 3-column sheets for 2x3 and 3x3 causal sweeps.
- `micro_grid`: many little tiles for broad scouting, color palettes, noisy alpha tests, and silhouette thumbnails.
- `square_moodboard`: square tiles for shape boards, material chips, and palette studies.
- `filmstrip`: ordered tiles for motion, time-of-day, long-exposure streak length, or camera path tests.

## Shape Sweeps

- silhouette: spindly, blocky, swept, squat, tall
- taper: cylinder, cone, bell, horn, fan
- density: sparse filaments, medium ribs, packed threads
- deformation: straight, bowed, twisted, turbulent
- scale: tiny detail, readable mid-form, huge framing shape

Shape sweeps should usually happen before material polish. If the thumbnail is not readable, the shader will not rescue it.

## Material Sweeps

- transparent emission: alpha crossed with strength
- smoke: density crossed with anisotropy
- glass or water: roughness crossed with caustic scale
- subsurface: radius crossed with color
- metal: roughness crossed with edge light strength

Keep one deliberate failure anchor in material sheets. It calibrates the eye and makes the good tile more legible.

## Color And Light Sweeps

- sunset haze: sky color, horizon color, haze density
- moonrise trail: streak warmth, halo radius, sky exposure
- caustics: light size, water roughness, pattern scale
- space plume: blue-white emission, soft gray shell, low fire color
- subsurface candy: opal, amber, ruby, sea-glass

Color sweeps should avoid one-note palettes. Put at least one cool/warm contrast or neutral anchor in the grid.

## Good First Sheets

- `plume_alpha_strength` x `plume_shape` with `micro_grid`
- `sunset_haze` as a one-axis `filmstrip`
- `subsurface_candy` x shape scale with `square_moodboard`
- caustic water scale x roughness with `balanced_grid`
- silhouette shape as unlabeled micro thumbnails, then rerun winners with labels
