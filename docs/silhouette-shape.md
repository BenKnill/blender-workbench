# Silhouette Shape Scout

Use the silhouette shape scout before material or lighting polish when the first question is whether the outline reads at thumbnail scale.

```bash
/Applications/Blender.app/Contents/MacOS/Blender --background --python examples/silhouette_shape_scout.py
```

The default contact sheet hides labels so the first choice is visual rather than name-led. After picking by tile position, use `metadata.json` or the generated README to map the pick back to an exact name.

```bash
/Applications/Blender.app/Contents/MacOS/Blender --background --python examples/silhouette_shape_scout.py -- --labels
/Applications/Blender.app/Contents/MacOS/Blender --background --python examples/silhouette_shape_scout.py -- --pick sil_swept
```

![Silhouette shape scout contact sheet](assets/silhouette-shape-scout.jpg)
