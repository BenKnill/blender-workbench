# Soft Atmosphere Cards

Use the soft atmosphere scout before placing horizon glow, haze sheets, or stylized light cards into selected renders.

```bash
/Applications/Blender.app/Contents/MacOS/Blender --background --python examples/soft_atmosphere_scout.py
```

The scout uses `blender_workbench.primitives.add_soft_horizon_band` to compare hard-edge failure, falloff width, alpha, glow strength, procedural breakup, and warm/cool color.

After inspecting the sheet, promote one candidate to selected-render scale:

```bash
/Applications/Blender.app/Contents/MacOS/Blender --background --python examples/soft_atmosphere_scout.py -- --pick soft_card_base_soft
```

Tiny tiles can hide card-edge artifacts. The selected render is the useful check before adding a haze or glow card to a larger scene.

![Soft atmosphere scout contact sheet](assets/soft-atmosphere-scout.jpg)
