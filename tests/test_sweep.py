import unittest

from blender_workbench.presets import SWEEP_AXES, TILE_PRESETS, one_axis_variants, two_axis_variants
from blender_workbench.sweep import SweepVariant, grid_variants, settings_to_jsonable


class SweepTests(unittest.TestCase):
    def test_grid_variants_are_row_major(self):
        variants = grid_variants(
            [("r0", {"a": 1}), ("r1", {"a": 2})],
            [("c0", {"b": 10}), ("c1", {"b": 20})],
            base={"base": True},
        )

        self.assertEqual([variant.name for variant in variants], ["r0_c0", "r0_c1", "r1_c0", "r1_c1"])
        self.assertEqual(variants[2].settings, {"base": True, "a": 2, "b": 10})

    def test_settings_to_jsonable_accepts_variant_settings(self):
        variant = SweepVariant("demo", {"alpha": 0.25})
        self.assertEqual(settings_to_jsonable(variant.settings), {"alpha": 0.25})

    def test_presets_offer_tile_and_axis_defaults(self):
        self.assertIn("plume_alpha_strength", SWEEP_AXES)
        self.assertIn("micro_grid", TILE_PRESETS)
        self.assertGreaterEqual(TILE_PRESETS["micro_grid"].columns, 6)

    def test_axis_helpers_merge_base_settings(self):
        variants = one_axis_variants(SWEEP_AXES["plume_shape"], base={"fixed_camera": True}, prefix="demo")

        self.assertEqual(len(variants), 3)
        self.assertEqual(variants[0].name, "demo_needle")
        self.assertTrue(variants[0].settings["fixed_camera"])

    def test_two_axis_helpers_create_grid(self):
        variants = two_axis_variants(
            SWEEP_AXES["plume_alpha_strength"],
            SWEEP_AXES["plume_shape"],
            base={"samples": 32},
        )

        self.assertEqual(len(variants), 9)
        self.assertEqual(variants[0].settings["samples"], 32)
        self.assertIn("shell_alpha", variants[0].settings)
        self.assertIn("width", variants[0].settings)


if __name__ == "__main__":
    unittest.main()
