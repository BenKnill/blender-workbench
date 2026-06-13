import unittest

from blender_workbench.recipes.sunset_haze import SunsetHazeSettings, coerce_sunset_haze_settings, sunset_haze_variants


class SunsetHazeTests(unittest.TestCase):
    def test_sunset_haze_variants_preserve_order_and_failures(self):
        variants = sunset_haze_variants(prefix="test")
        names = [variant.name for variant in variants]

        self.assertEqual(
            names,
            [
                "test_flat_fail",
                "test_violet_dust",
                "test_peach_moonrise",
                "test_blue_afterglow",
                "test_orange_fail",
                "test_washout_fail",
            ],
        )
        self.assertLess(variants[0].settings["haze_density"], variants[-1].settings["haze_density"])
        self.assertGreater(variants[-1].settings["disk_strength"], variants[1].settings["disk_strength"])

    def test_sunset_haze_settings_coerce_known_fields(self):
        settings = coerce_sunset_haze_settings({"haze_density": 0.05, "disk_height": 0.92, "unused": True})

        self.assertIsInstance(settings, SunsetHazeSettings)
        self.assertEqual(settings.haze_density, 0.05)
        self.assertEqual(settings.disk_height, 0.92)
        self.assertFalse(hasattr(settings, "unused"))


if __name__ == "__main__":
    unittest.main()
