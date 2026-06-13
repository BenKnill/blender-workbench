import json
import tempfile
import unittest
from pathlib import Path

import blender_workbench.sweep as sweep_module
from blender_workbench.recipes.long_exposure_moonrise import (
    LongExposureMoonriseSettings,
    coerce_long_exposure_moonrise_settings,
    long_exposure_moonrise_variants,
    moonrise_trail_descriptor,
)
from blender_workbench.sweep import RenderConfig, RenderResult, render_sweep


class LongExposureMoonriseTests(unittest.TestCase):
    def test_long_exposure_variants_record_axes_and_failures(self):
        variants = long_exposure_moonrise_variants(prefix="test")

        self.assertEqual(len(variants), 11)
        self.assertEqual(variants[1].name, "test_balanced_rise")
        self.assertEqual(variants[1].role, "baseline")
        self.assertIn("long_exposure_moonrise", variants[0].tags)
        failures = [variant for variant in variants if variant.role == "failure_anchor"]
        self.assertEqual({variant.label for variant in failures}, {"torch_fail", "flat_bar_fail", "washout_fail"})

        long_warm = next(variant for variant in variants if variant.label == "long_warm")
        broad_halo = next(variant for variant in variants if variant.label == "broad_halo")
        washout = next(variant for variant in variants if variant.label == "washout_fail")
        self.assertGreater(long_warm.settings["moonrise_trail"]["streak_length"], variants[1].settings["moonrise_trail"]["streak_length"])
        self.assertGreater(broad_halo.settings["moonrise_trail"]["halo_radius"], variants[1].settings["moonrise_trail"]["halo_radius"])
        self.assertGreater(washout.settings["moonrise_trail"]["sky_exposure"], variants[1].settings["moonrise_trail"]["sky_exposure"])

    def test_coerce_settings_and_descriptor_ignore_unknown_keys(self):
        settings = coerce_long_exposure_moonrise_settings({"streak_length": 2.1, "moon_warmth": 0.8, "unused": True})
        descriptor = moonrise_trail_descriptor(settings)

        self.assertIsInstance(settings, LongExposureMoonriseSettings)
        self.assertEqual(settings.streak_length, 2.1)
        self.assertEqual(settings.moon_warmth, 0.8)
        self.assertNotIn("unused", settings.__dict__)
        self.assertEqual(descriptor["technique"], "cheap_emissive_geometry")
        self.assertFalse(descriptor["physical_motion_blur"])
        self.assertEqual(descriptor["moon_warmth"], 0.8)

    def test_render_sweep_preserves_trail_metadata_without_blender(self):
        original_render_variant = sweep_module._render_variant
        original_write_contact_sheet = sweep_module.write_contact_sheet
        original_write_sweep_diagnostics = sweep_module.write_sweep_diagnostics

        def fake_render_variant(**kwargs):
            raw = kwargs["out_dir"] / f"{kwargs['variant'].name}.raw.png"
            raw.write_text("image")
            return RenderResult(
                name=kwargs["variant"].name,
                raw=str(raw.relative_to(kwargs["root"])),
                finished=None,
                settings=kwargs["variant"].settings,
                label=kwargs["variant"].label,
                note=kwargs["variant"].note,
                role=kwargs["variant"].role,
                tags=kwargs["variant"].tags,
            )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_dir = root / "examples/output/long_exposure_moonrise"
            variants = long_exposure_moonrise_variants(prefix="moontrail")[:4]
            sweep_module._render_variant = fake_render_variant
            sweep_module.write_contact_sheet = lambda *_args, **_kwargs: None
            sweep_module.write_sweep_diagnostics = lambda *_args, **_kwargs: {"warnings": []}
            try:
                render_sweep(
                    variants=variants,
                    build_scene=lambda _settings: None,
                    out_dir=out_dir,
                    root=root,
                    config=RenderConfig(),
                    postprocess=None,
                    title="Long Exposure Moonrise Test",
                )
            finally:
                sweep_module._render_variant = original_render_variant
                sweep_module.write_contact_sheet = original_write_contact_sheet
                sweep_module.write_sweep_diagnostics = original_write_sweep_diagnostics

            metadata = json.loads((out_dir / "metadata.json").read_text())

        self.assertEqual(metadata["variants"][0]["settings"]["moonrise_trail"]["technique"], "cheap_emissive_geometry")
        self.assertEqual(metadata["workflow"]["pick_handles"][1]["role"], "baseline")
        self.assertEqual(metadata["variants"][2]["settings"]["moonrise_trail"]["moon_warmth"], 0.72)
        self.assertEqual(metadata["variants"][3]["settings"]["moonrise_trail"]["streak_angle"], 18.0)


if __name__ == "__main__":
    unittest.main()
