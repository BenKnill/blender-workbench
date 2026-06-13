import unittest

from blender_workbench.presets import RENDER_PRESETS, SWEEP_AXES, TILE_PRESETS, one_axis_variants, stride_axis, two_axis_variants
from blender_workbench.recipes.rocket_plume import (
    RocketPlumeSettings,
    coerce_rocket_plume_settings,
    rocket_plume_scout_variants,
    rocket_plume_texture_variants,
)
from blender_workbench.sweep import RenderConfig, SweepVariant, TileSpec, grid_variants, named_variants, settings_to_jsonable


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
        self.assertIn("light_source_jitter", SWEEP_AXES)
        self.assertIn("texture_magnitude", SWEEP_AXES)
        self.assertIn("texture_magnitude_stride", SWEEP_AXES)
        self.assertIn("micro_grid", TILE_PRESETS)
        self.assertIn("auto_micro_grid", TILE_PRESETS)
        self.assertIn("auto_tiny_grid", TILE_PRESETS)
        self.assertIn("shape_scout", RENDER_PRESETS)
        self.assertGreaterEqual(TILE_PRESETS["micro_grid"].columns, 6)
        self.assertIsNone(TILE_PRESETS["auto_micro_grid"].columns)
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

    def test_named_variants_are_lightweight_case_boards(self):
        variants = named_variants(
            {
                "clean": {"texture_magnitude": 0.0},
                "rugged": {"texture_magnitude": 0.7},
            },
            base={"fixed_camera": True},
            prefix="mat",
        )

        self.assertEqual([variant.name for variant in variants], ["mat_clean", "mat_rugged"])
        self.assertEqual(variants[1].label, "rugged")
        self.assertTrue(variants[1].settings["fixed_camera"])

    def test_tile_spec_auto_columns_make_square_boards(self):
        tile = TileSpec.auto_micro_grid()

        self.assertEqual(TileSpec().width, TileSpec().height)
        self.assertIsNone(TileSpec().columns)
        self.assertEqual(tile.width, tile.height)
        self.assertEqual(tile.columns_for_count(1), 1)
        self.assertEqual(tile.columns_for_count(4), 2)
        self.assertEqual(tile.columns_for_count(9), 3)
        self.assertEqual(tile.columns_for_count(10), 4)

    def test_stride_axis_makes_stride_adjustment_obvious(self):
        axis = stride_axis("demo_stride", "texture_magnitude", center=0.5, stride=0.25, steps=(-2, 0, 2), clamp_min=0.0)

        self.assertEqual([label for label, _ in axis.values], ["m2", "base", "p2"])
        self.assertEqual([settings["texture_magnitude"] for _, settings in axis.values], [0.0, 0.5, 1.0])

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

    def test_rocket_plume_texture_scout_has_failure_anchor(self):
        variants = rocket_plume_texture_variants(prefix="test")
        names = [variant.name for variant in variants]

        self.assertEqual(len(variants), 16)
        self.assertIn("test_overdone", names)
        self.assertEqual(variants[-1].name, "test_whiteout_fail")
        self.assertGreater(variants[-1].settings["plume_texture_magnitude"], variants[0].settings["plume_texture_magnitude"])
        self.assertGreater(variants[-1].settings["density_wisp_count"], variants[0].settings["density_wisp_count"])
        self.assertGreater(variants[-1].settings["density_clump_count"], variants[0].settings["density_clump_count"])
        self.assertIn("filament_wiggle", variants[-1].settings)


if __name__ == "__main__":
    unittest.main()
