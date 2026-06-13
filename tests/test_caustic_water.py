import json
import tempfile
import unittest
from pathlib import Path

import blender_workbench.sweep as sweep_module
from blender_workbench.recipes.caustic_water import (
    CausticWaterSettings,
    caustic_water_descriptor,
    caustic_water_variants,
    coerce_caustic_water_settings,
)
from blender_workbench.sweep import RenderConfig, RenderResult, render_sweep


class CausticWaterTests(unittest.TestCase):
    def test_caustic_water_variants_record_axes_and_failures(self):
        variants = caustic_water_variants(prefix="test")

        self.assertEqual(len(variants), 11)
        self.assertEqual(variants[0].name, "test_pool_balanced")
        self.assertEqual(variants[0].role, "baseline")
        self.assertIn("caustic_water", variants[0].tags)
        failures = [variant for variant in variants if variant.role == "failure_anchor"]
        self.assertEqual({variant.label for variant in failures}, {"zebra_fail", "washed_blur_fail", "blue_blob_fail"})

        tight = next(variant for variant in variants if variant.label == "tight_ripples")
        soft = next(variant for variant in variants if variant.label == "soft_large_light")
        zebra = next(variant for variant in variants if variant.label == "zebra_fail")
        washed = next(variant for variant in variants if variant.label == "washed_blur_fail")
        self.assertGreater(tight.settings["caustic_water"]["caustic_scale"], variants[0].settings["caustic_water"]["caustic_scale"])
        self.assertGreater(soft.settings["caustic_water"]["light_size"], variants[0].settings["caustic_water"]["light_size"])
        self.assertGreater(zebra.settings["caustic_water"]["caustic_contrast"], variants[0].settings["caustic_water"]["caustic_contrast"])
        self.assertGreater(washed.settings["caustic_water"]["water_roughness"], variants[0].settings["caustic_water"]["water_roughness"])

    def test_coerce_settings_and_descriptor_ignore_unknown_keys(self):
        settings = coerce_caustic_water_settings({"water_roughness": 0.12, "caustic_scale": 11.0, "unused": True})
        descriptor = caustic_water_descriptor(settings)

        self.assertIsInstance(settings, CausticWaterSettings)
        self.assertEqual(settings.water_roughness, 0.12)
        self.assertEqual(settings.caustic_scale, 11.0)
        self.assertNotIn("unused", settings.__dict__)
        self.assertEqual(descriptor["technique"], "fake_procedural_caustic_ribbons")
        self.assertFalse(descriptor["physical_caustics"])
        self.assertIn("structured_floor_grid", descriptor["diagnostics"])

    def test_render_sweep_preserves_caustic_metadata_without_blender(self):
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
            out_dir = root / "examples/output/caustic_water"
            variants = caustic_water_variants(prefix="caustic")[:4]
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
                    title="Caustic Water Test",
                )
            finally:
                sweep_module._render_variant = original_render_variant
                sweep_module.write_contact_sheet = original_write_contact_sheet
                sweep_module.write_sweep_diagnostics = original_write_sweep_diagnostics

            metadata = json.loads((out_dir / "metadata.json").read_text())

        self.assertEqual(metadata["variants"][0]["settings"]["caustic_water"]["technique"], "fake_procedural_caustic_ribbons")
        self.assertEqual(metadata["workflow"]["pick_handles"][0]["role"], "baseline")
        self.assertEqual(metadata["variants"][1]["settings"]["caustic_water"]["caustic_scale"], 18.0)
        self.assertEqual(metadata["variants"][3]["settings"]["caustic_water"]["light_size"], 1.8)


if __name__ == "__main__":
    unittest.main()
