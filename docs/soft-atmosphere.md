# Soft Atmosphere Cards

Use the soft atmosphere scout before placing horizon glow, haze sheets, or stylized light cards into selected renders.

```bash
/Applications/Blender.app/Contents/MacOS/Blender --background --python examples/soft_atmosphere_scout.py
```

The scout uses `blender_workbench.primitives.add_soft_horizon_band` to compare hard-edge failure, falloff width, alpha, glow strength, procedural breakup, and warm/cool color.

![Soft atmosphere scout contact sheet](assets/soft-atmosphere-scout.jpg)
