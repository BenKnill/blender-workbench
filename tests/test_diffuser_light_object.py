import json
import tempfile
import unittest
from pathlib import Path

import blender_workbench.sweep as sweep_module
from blender_workbench.recipes.diffuser_light_object import (
    DiffuserLightObjectSettings,
    coerce_diffuser_light_object_settings,
    diffuser_light_object_descriptor,
    diffuser_light_object_variants,
)
from blender_workbench.sweep import RenderConfig, RenderResult, render_sweep


class DiffuserLightObjectTests(unittest.TestCase):
    def test_diffuser_light_object_variants_record_shapes_patterns_and_failures(self):
        variants = diffuser_light_object_variants(prefix="test")

        self.assertEqual(len(variants), 11)
        self.assertEqual(variants[0].name, "test_china_ball")
        self.assertEqual(variants[0].role, "baseline")
        self.assertIn("diffuser_light_object", variants[0].tags)
        shapes = {variant.settings["diffuser_object"]["shell_shape"] for variant in variants}
        self.assertEqual(shapes, {"sphere", "cylinder", "faceted", "organic"})
        failures = [variant for variant in variants if variant.role == "failure_anchor"]
        self.assertEqual({variant.label for variant in failures}, {"opaque_prop_fail", "overbright_ball_fail", "overprinted_fail"})

        dense = next(variant for variant in variants if variant.label == "dense_print")
        overprinted = next(variant for variant in variants if variant.label == "overprinted_fail")
        opaque = next(variant for variant in variants if variant.label == "opaque_prop_fail")
        self.assertGreater(dense.settings["diffuser_object"]["pattern_density"], variants[0].settings["diffuser_object"]["pattern_density"])
        self.assertGreater(overprinted.settings["diffuser_object"]["pattern_magnitude"], dense.settings["diffuser_object"]["pattern_magnitude"])
        self.assertGreater(opaque.settings["diffuser_object"]["shell_opacity"], variants[0].settings["diffuser_object"]["shell_opacity"])

    def test_coerce_settings_and_descriptor_ignore_unknown_keys(self):
        settings = coerce_diffuser_light_object_settings({"shell_shape": "faceted", "pattern_density": 9, "unused": True})
        descriptor = diffuser_light_object_descriptor(settings)

        self.assertIsInstance(settings, DiffuserLightObjectSettings)
        self.assertEqual(settings.shell_shape, "faceted")
        self.assertEqual(settings.pattern_density, 9)
        self.assertNotIn("unused", settings.__dict__)
        self.assertEqual(descriptor["shell_shape"], "faceted")
        self.assertEqual(descriptor["available_shell_shapes"], ("sphere", "cylinder", "faceted", "organic"))
        self.assertIn("glossy_tinted_object", descriptor["diagnostic_receivers"])

    def test_render_sweep_preserves_diffuser_metadata_without_blender(self):
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
            out_dir = root / "examples/output/diffuser_light_object"
            variants = diffuser_light_object_variants(prefix="diffuser")[:5]
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
                    title="Diffuser Light Object Test",
                )
            finally:
                sweep_module._render_variant = original_render_variant
                sweep_module.write_contact_sheet = original_write_contact_sheet
                sweep_module.write_sweep_diagnostics = original_write_sweep_diagnostics

            metadata = json.loads((out_dir / "metadata.json").read_text())

        self.assertEqual(metadata["variants"][0]["settings"]["diffuser_object"]["technique"], "visible_translucent_diffuser_object")
        self.assertEqual(metadata["workflow"]["pick_handles"][0]["role"], "baseline")
        self.assertEqual(metadata["variants"][2]["settings"]["diffuser_object"]["shell_shape"], "cylinder")
        self.assertEqual(metadata["variants"][4]["settings"]["diffuser_object"]["shell_shape"], "faceted")


if __name__ == "__main__":
    unittest.main()
