import unittest

from blender_workbench.recipes.soft_atmosphere import SoftAtmosphereSettings, coerce_soft_atmosphere_settings, soft_atmosphere_variants


class SoftAtmosphereTests(unittest.TestCase):
    def test_soft_atmosphere_recipe_exposes_card_tuning_board(self):
        variants = soft_atmosphere_variants(prefix="test")
        settings = coerce_soft_atmosphere_settings({"noise_strength": 0.2, "center_fraction": 0.5, "unused": True})
        names = [variant.name for variant in variants]

        self.assertEqual(len(variants), 12)
        self.assertIn("test_hard_edge_fail", names)
        self.assertIn("test_wide_falloff", names)
        self.assertIn("test_fine_noise", names)
        self.assertIn("test_hot_glow", names)
        self.assertIsInstance(settings, SoftAtmosphereSettings)
        self.assertEqual(settings.noise_strength, 0.2)
        self.assertEqual(settings.center_fraction, 0.5)
        self.assertFalse(hasattr(settings, "unused"))


if __name__ == "__main__":
    unittest.main()
