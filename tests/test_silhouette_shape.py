import unittest
from pathlib import Path

from blender_workbench.example_manifest import load_manifest
from blender_workbench.recipes.silhouette_shape import (
    SilhouetteShapeSettings,
    coerce_silhouette_shape_settings,
    silhouette_shape_variants,
)
from blender_workbench.sweep import TileSpec


class SilhouetteShapeTests(unittest.TestCase):
    def test_tile_spec_can_hide_labels_for_blind_boards(self):
        tile = TileSpec.auto_tiny_grid().without_labels()

        self.assertFalse(tile.show_labels)
        self.assertEqual(tile.label_height, 0)
        self.assertEqual(tile.width, tile.height)
        self.assertIsNone(tile.columns)

    def test_silhouette_shape_variants_include_failure_anchor(self):
        variants = silhouette_shape_variants(prefix="test")
        settings = coerce_silhouette_shape_settings({"lean": -10.0, "unused": True})
        names = [variant.name for variant in variants]

        self.assertEqual(len(variants), 6)
        self.assertIn("test_spindly", names)
        self.assertIn("test_blocky", names)
        self.assertIn("test_cropped_fail", names)
        self.assertIsInstance(settings, SilhouetteShapeSettings)
        self.assertEqual(settings.lean, -10.0)
        self.assertFalse(hasattr(settings, "unused"))

    def test_real_manifest_lists_every_top_level_example_script(self):
        root = Path.cwd()
        examples = load_manifest(root=root)
        manifest_scripts = {example["script"] for example in examples}
        actual_scripts = {str(path.relative_to(root)) for path in (root / "examples").glob("*.py")}

        self.assertEqual(actual_scripts - manifest_scripts, set())


if __name__ == "__main__":
    unittest.main()
