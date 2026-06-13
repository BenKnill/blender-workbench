import json
import tempfile
import unittest
from pathlib import Path

import blender_workbench.sweep as sweep_module
from blender_workbench.recipes.layered_material import (
    LayeredMaterialSettings,
    coerce_layered_material_settings,
    layered_material_variants,
    layered_material_weight_summary,
)
from blender_workbench.sweep import RenderConfig, RenderResult, render_sweep


class LayeredMaterialTests(unittest.TestCase):
    def test_layered_material_variants_expose_component_weights(self):
        variants = layered_material_variants(prefix="test")

        self.assertEqual(len(variants), 10)
        self.assertEqual(variants[0].name, "test_diffuse_only")
        self.assertEqual(variants[0].role, "baseline")
        self.assertEqual(variants[-1].role, "failure_anchor")
        self.assertIn("layered_material", variants[0].tags)
        balanced = next(variant for variant in variants if variant.label == "balanced_skin")
        self.assertEqual(balanced.settings["component"], "balanced_skin")
        self.assertEqual(balanced.settings["layer_weights"]["epidermal_sss"], balanced.settings["epidermal_sss_weight"])
        self.assertGreater(balanced.settings["soft_specular_weight"], balanced.settings["wet_specular_weight"])

    def test_coerce_settings_and_weight_summary_ignore_unknown_keys(self):
        settings = coerce_layered_material_settings({"component": "demo", "dermal_sss_weight": 0.7, "unused": True})
        weights = layered_material_weight_summary(settings)

        self.assertIsInstance(settings, LayeredMaterialSettings)
        self.assertEqual(settings.component, "demo")
        self.assertEqual(settings.dermal_sss_weight, 0.7)
        self.assertNotIn("unused", settings.__dict__)
        self.assertEqual(weights["dermal_sss"], 0.7)
        self.assertIn("wet_specular", weights)

    def test_render_sweep_preserves_layer_metadata_without_blender(self):
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
            out_dir = root / "examples/output/layered_material"
            variants = layered_material_variants(prefix="layer")[:3]
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
                    title="Layered Material Test",
                )
            finally:
                sweep_module._render_variant = original_render_variant
                sweep_module.write_contact_sheet = original_write_contact_sheet
                sweep_module.write_sweep_diagnostics = original_write_sweep_diagnostics

            metadata = json.loads((out_dir / "metadata.json").read_text())

        self.assertEqual(metadata["variants"][0]["settings"]["component"], "base_unscattered_diffuse")
        self.assertEqual(metadata["variants"][0]["settings"]["layer_weights"]["diffuse"], 1.0)
        self.assertEqual(metadata["workflow"]["pick_handles"][0]["role"], "baseline")
        self.assertEqual(metadata["variants"][2]["settings"]["layer_weights"]["backscatter"], 0.78)


if __name__ == "__main__":
    unittest.main()
