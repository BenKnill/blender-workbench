import unittest

from blender_workbench.presets import RENDER_PRESETS, SWEEP_AXES, TILE_PRESETS, one_axis_variants, two_axis_variants
from blender_workbench.recipes.rocket_plume import RocketPlumeSettings, coerce_rocket_plume_settings, rocket_plume_scout_variants
from blender_workbench.sweep import RenderConfig, SweepVariant, grid_variants, settings_to_jsonable


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
        self.assertIn("shape_scout", RENDER_PRESETS)
        self.assertGreaterEqual(TILE_PRESETS["micro_grid"].columns, 6)
        self.assertLessEqual(RENDER_PRESETS["shape_scout"].samples, 1)

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

    def test_render_config_profiles_are_ordered_by_cost(self):
        self.assertEqual(RenderConfig.shape_scout().engine, "BLENDER_WORKBENCH")
        self.assertEqual(RenderConfig.material_scout().engine, "EEVEE")
        self.assertLess(RenderConfig.shape_scout().resolution_x, RenderConfig.hero_check().resolution_x)
        self.assertLess(RenderConfig.cycles_preview().samples, RenderConfig.hero_check().samples)

    def test_settings_to_jsonable_serializes_render_config(self):
        config = RenderConfig.cycles_preview()
        data = settings_to_jsonable(config)

        self.assertEqual(data["engine"], "CYCLES")
        self.assertEqual(data["transparent_max_bounces"], 18)
        self.assertIn("tile", data)

    def test_rocket_plume_recipe_coerces_known_settings(self):
        settings = coerce_rocket_plume_settings({"width": 1.7, "length": 0.8, "samples": 99})

        self.assertIsInstance(settings, RocketPlumeSettings)
        self.assertEqual(settings.width, 1.7)
        self.assertEqual(settings.length, 0.8)
        self.assertFalse(hasattr(settings, "samples"))

    def test_rocket_plume_scout_is_three_by_three(self):
        variants = rocket_plume_scout_variants(prefix="test")

        self.assertEqual(len(variants), 9)
        self.assertEqual(variants[0].name, "test_ghost_needle")
        self.assertIn("shell_alpha", variants[0].settings)
        self.assertIn("width", variants[0].settings)


if __name__ == "__main__":
    unittest.main()
