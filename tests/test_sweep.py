import unittest

from blender_workbench.camera import camera_distance_for_matching_framing, orbit_location
from blender_workbench.presets import RENDER_PRESETS, SWEEP_AXES, TILE_PRESETS, one_axis_variants, stride_axis, two_axis_variants
from blender_workbench.recipes.camera_perspective import (
    CameraPerspectiveSettings,
    camera_perspective_variants,
    coerce_camera_perspective_settings,
)
from blender_workbench.recipes.gobo_lighting import GoboLightingSettings, coerce_gobo_settings, gobo_lighting_variants
from blender_workbench.recipes.mesh_light import MeshLightSettings, coerce_mesh_light_settings, mesh_light_variants
from blender_workbench.recipes.rocket_plume import (
    RocketPlumeSettings,
    coerce_rocket_plume_settings,
    rocket_plume_scout_variants,
    rocket_plume_texture_variants,
)
from blender_workbench.recipes.subsurface import SubsurfaceSettings, coerce_subsurface_settings, subsurface_variants
from blender_workbench.recipes.terrain_environment import (
    TerrainEnvironmentSettings,
    coerce_terrain_environment_settings,
    terrain_environment_variants,
)
from blender_workbench.recipes.transparency import TransparencySettings, coerce_transparency_settings, transparency_variants
from blender_workbench.sweep import RenderConfig, SweepVariant, TileSpec, grid_variants, named_variants, select_variant, settings_to_jsonable


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
        self.assertIn("camera_perspective", SWEEP_AXES)
        self.assertIn("camera_orbit", SWEEP_AXES)
        self.assertIn("transparency_alpha", SWEEP_AXES)
        self.assertIn("micro_grid", TILE_PRESETS)
        self.assertIn("auto_micro_grid", TILE_PRESETS)
        self.assertIn("auto_tiny_grid", TILE_PRESETS)
        self.assertIn("shape_scout", RENDER_PRESETS)
        self.assertGreaterEqual(TILE_PRESETS["micro_grid"].columns, 6)
        self.assertIsNone(TILE_PRESETS["auto_micro_grid"].columns)
        self.assertLessEqual(RENDER_PRESETS["shape_scout"].samples, 1)

    def test_camera_helpers_match_framing_and_orbit(self):
        self.assertEqual(camera_distance_for_matching_framing(90, base_lens_mm=45, base_distance=4), 8)
        location = orbit_location(target=(0, 0, 0), distance=2, yaw_degrees=0, pitch_degrees=0)

        self.assertAlmostEqual(location[0], 0)
        self.assertAlmostEqual(location[1], -2)
        self.assertAlmostEqual(location[2], 0)

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

    def test_select_variant_accepts_index_name_or_label(self):
        variants = [
            SweepVariant("wide_shell", {"width": 1.4}, label="wide"),
            SweepVariant("soft_fill", {"fill": 0.8}, label="soft"),
        ]

        self.assertEqual(select_variant(variants, 1).name, "wide_shell")
        self.assertEqual(select_variant(variants, "2").name, "soft_fill")
        self.assertEqual(select_variant(variants, "wide_shell").settings["width"], 1.4)
        self.assertEqual(select_variant(variants, "soft").name, "soft_fill")

    def test_select_variant_reports_unknown_picks(self):
        variants = [SweepVariant("wide_shell", {"width": 1.4})]

        with self.assertRaisesRegex(ValueError, "Unknown variant"):
            select_variant(variants, "missing")

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

    def test_gobo_recipe_exposes_dense_lighting_board(self):
        variants = gobo_lighting_variants(prefix="test")
        settings = coerce_gobo_settings({"pattern": "dots", "light_size": 0.4, "unused": True})

        self.assertEqual(len(variants), 16)
        self.assertIsInstance(settings, GoboLightingSettings)
        self.assertEqual(settings.pattern, "dots")
        self.assertEqual(settings.light_size, 0.4)
        self.assertFalse(hasattr(settings, "unused"))

    def test_subsurface_recipe_exposes_dense_material_board(self):
        variants = subsurface_variants(prefix="test")
        settings = coerce_subsurface_settings({"subsurface_weight": 0.5, "core_light_energy": 99, "unused": True})
        names = [variant.name for variant in variants]

        self.assertEqual(len(variants), 16)
        self.assertIn("test_matte_fail", names)
        self.assertIn("test_overdone", names)
        self.assertIsInstance(settings, SubsurfaceSettings)
        self.assertEqual(settings.subsurface_weight, 0.5)
        self.assertEqual(settings.core_light_energy, 99)
        self.assertFalse(hasattr(settings, "unused"))

    def test_mesh_light_recipe_exposes_same_view_lighting_board(self):
        variants = mesh_light_variants(prefix="test")
        settings = coerce_mesh_light_settings({"panel_width": 2.0, "fill_strength": 12.0, "unused": True})
        names = [variant.name for variant in variants]

        self.assertEqual(len(variants), 25)
        self.assertIn("test_size_m2", names)
        self.assertIn("test_dist_p2", names)
        self.assertIn("test_height_base", names)
        self.assertIn("test_fill_p2", names)
        self.assertIn("test_gel_m2", names)
        self.assertIsInstance(settings, MeshLightSettings)
        self.assertEqual(settings.panel_width, 2.0)
        self.assertEqual(settings.fill_strength, 12.0)
        self.assertFalse(hasattr(settings, "unused"))

    def test_terrain_environment_recipe_exposes_landscape_board(self):
        variants = terrain_environment_variants(prefix="test")
        settings = coerce_terrain_environment_settings({"terrain_relief": 0.8, "haze_alpha": 0.4, "unused": True})
        names = [variant.name for variant in variants]

        self.assertEqual(len(variants), 25)
        self.assertIn("test_relief_m2", names)
        self.assertIn("test_strata_p2", names)
        self.assertIn("test_haze_base", names)
        self.assertIn("test_light_p1", names)
        self.assertIn("test_fg_p2", names)
        self.assertIsInstance(settings, TerrainEnvironmentSettings)
        self.assertEqual(settings.terrain_relief, 0.8)
        self.assertEqual(settings.haze_alpha, 0.4)
        self.assertFalse(hasattr(settings, "unused"))

    def test_camera_perspective_recipe_exposes_lens_distance_board(self):
        variants = camera_perspective_variants(prefix="test")
        settings = coerce_camera_perspective_settings({"camera_lens": 24, "subject_y": 0.4, "unused": True})
        names = [variant.name for variant in variants]

        self.assertEqual(len(variants), 25)
        self.assertIn("test_lens_m2", names)
        self.assertIn("test_fg_p2", names)
        self.assertIn("test_bg_p2", names)
        self.assertIn("test_grid_p2", names)
        self.assertIn("test_subj_p2", names)
        self.assertIsInstance(settings, CameraPerspectiveSettings)
        self.assertEqual(settings.camera_lens, 24)
        self.assertEqual(settings.subject_y, 0.4)
        self.assertFalse(hasattr(settings, "unused"))

    def test_camera_perspective_recipe_keeps_same_view_by_default(self):
        variants = camera_perspective_variants(prefix="test")

        self.assertTrue(all(variant.settings["camera_yaw"] == 0 for variant in variants))
        self.assertTrue(all(variant.settings["camera_roll"] == 0 for variant in variants))
        self.assertEqual([variant.label.split("_")[0] for variant in variants[5:10]], ["fg"] * 5)

    def test_camera_perspective_recipe_accepts_stride_adjustment(self):
        timid = camera_perspective_variants(prefix="test", lens_stride=8)
        loud = camera_perspective_variants(prefix="test", lens_stride=40)
        timid_depth = camera_perspective_variants(prefix="test", foreground_stride=0.12)
        loud_depth = camera_perspective_variants(prefix="test", foreground_stride=0.6)

        self.assertLess(timid[0].settings["camera_lens"], timid[2].settings["camera_lens"])
        self.assertLess(loud[0].settings["camera_lens"], timid[0].settings["camera_lens"])
        self.assertGreater(loud[4].settings["camera_distance"], timid[4].settings["camera_distance"])
        self.assertLess(loud_depth[5].settings["foreground_depth"], timid_depth[5].settings["foreground_depth"])
        self.assertGreater(loud_depth[9].settings["foreground_depth"], timid_depth[9].settings["foreground_depth"])

    def test_transparency_recipe_exposes_dense_material_board(self):
        variants = transparency_variants(prefix="test")
        settings = coerce_transparency_settings({"alpha": 0.25, "ior": 1.8, "unused": True})
        names = [variant.name for variant in variants]

        self.assertEqual(len(variants), 25)
        self.assertIn("test_alpha_m2", names)
        self.assertIn("test_ior_p2", names)
        self.assertIn("test_tint_p2", names)
        self.assertIsInstance(settings, TransparencySettings)
        self.assertEqual(settings.alpha, 0.25)
        self.assertEqual(settings.ior, 1.8)
        self.assertFalse(hasattr(settings, "unused"))

    def test_transparency_recipe_accepts_stride_adjustment(self):
        timid = transparency_variants(prefix="test", alpha_stride=0.08, ior_stride=0.12)
        loud = transparency_variants(prefix="test", alpha_stride=0.4, ior_stride=0.55)

        self.assertGreater(timid[0].settings["alpha"], loud[0].settings["alpha"])
        self.assertGreater(timid[10].settings["ior"], loud[10].settings["ior"])
        self.assertGreater(loud[14].settings["ior"], timid[14].settings["ior"])


if __name__ == "__main__":
    unittest.main()
