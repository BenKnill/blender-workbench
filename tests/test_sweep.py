import unittest

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


if __name__ == "__main__":
    unittest.main()
