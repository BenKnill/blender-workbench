# Sunset Haze Filmstrip

Use this scout when the question is static dusk, moonrise, or afterglow atmosphere rather than moving moon trails.

```bash
/Applications/Blender.app/Contents/MacOS/Blender --background --python examples/sunset_haze_scout.py
```

The filmstrip preserves order: flat failure, the three `SUNSET_HAZE` presets, over-orange failure, and washout failure. Promote one tile before carrying the mood into a heavier scene:

```bash
/Applications/Blender.app/Contents/MacOS/Blender --background --python examples/sunset_haze_scout.py -- --pick sunset_peach_moonrise
```

![Sunset haze scout contact sheet](assets/sunset-haze-scout.jpg)
