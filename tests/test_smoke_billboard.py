import json
import tempfile
import unittest
from pathlib import Path

import blender_workbench.sweep as sweep_module
from blender_workbench.recipes.smoke_billboard import (
    SmokeBillboardSettings,
    coerce_smoke_billboard_settings,
    smoke_billboard_descriptor,
    smoke_billboard_variants,
)
from blender_workbench.sweep import RenderConfig, RenderResult, render_sweep


class SmokeBillboardTests(unittest.TestCase):
    def test_smoke_billboard_variants_record_layer_and_failure_anchors(self):
        variants = smoke_billboard_variants(prefix="test")

        self.assertEqual(len(variants), 11)
        self.assertEqual(variants[0].name, "test_thin_haze")
        self.assertEqual(variants[0].role, "baseline")
        self.assertIn("smoke_billboard", variants[0].tags)
        failures = [variant for variant in variants if variant.role == "failure_anchor"]
        self.assertEqual({variant.label for variant in failures}, {"invisible_haze_fail", "dirty_card_fail", "opaque_wall_fail"})
        dense = next(variant for variant in variants if variant.label == "dense_depth")
        wide = next(variant for variant in variants if variant.label == "wide_parallax")
        opaque = next(variant for variant in variants if variant.label == "opaque_wall_fail")
        invisible = next(variant for variant in variants if variant.label == "invisible_haze_fail")

        self.assertGreater(dense.settings["billboard_stack"]["layer_count"], variants[0].settings["billboard_stack"]["layer_count"])
        self.assertGreater(wide.settings["billboard_stack"]["parallax"], variants[0].settings["billboard_stack"]["parallax"])
        self.assertGreater(opaque.settings["billboard_stack"]["per_layer_alpha"], variants[0].settings["billboard_stack"]["per_layer_alpha"])
        self.assertLess(invisible.settings["billboard_stack"]["per_layer_alpha"], variants[0].settings["billboard_stack"]["per_layer_alpha"])
        self.assertFalse(variants[0].settings["billboard_stack"]["volume_simulation"])

    def test_coerce_settings_and_descriptor_ignore_unknown_keys(self):
        settings = coerce_smoke_billboard_settings({"alpha": 0.25, "billboard_mode": "camera_facing", "unused": True})
        descriptor = smoke_billboard_descriptor(settings)

        self.assertIsInstance(settings, SmokeBillboardSettings)
        self.assertEqual(settings.alpha, 0.25)
        self.assertEqual(settings.billboard_mode, "camera_facing")
        self.assertNotIn("unused", settings.__dict__)
        self.assertEqual(descriptor["billboard_mode"], "camera_facing")
        self.assertEqual(descriptor["per_layer_alpha"], 0.25)
        self.assertEqual(descriptor["technique"], "transparent_alpha_billboards")

    def test_render_sweep_preserves_billboard_metadata_without_blender(self):
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
            out_dir = root / "examples/output/smoke_billboard"
            variants = smoke_billboard_variants(prefix="smoke")[:4]
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
                    title="Smoke Billboard Test",
                )
            finally:
                sweep_module._render_variant = original_render_variant
                sweep_module.write_contact_sheet = original_write_contact_sheet
                sweep_module.write_sweep_diagnostics = original_write_sweep_diagnostics

            metadata = json.loads((out_dir / "metadata.json").read_text())

        self.assertEqual(metadata["variants"][0]["settings"]["billboard_stack"]["technique"], "transparent_alpha_billboards")
        self.assertEqual(metadata["variants"][0]["settings"]["billboard_stack"]["diagnostics"][0], "foreground_markers")
        self.assertEqual(metadata["workflow"]["pick_handles"][0]["role"], "baseline")
        self.assertEqual(metadata["variants"][3]["settings"]["billboard_stack"]["fake_forward_scatter"], 0.66)


if __name__ == "__main__":
    unittest.main()
