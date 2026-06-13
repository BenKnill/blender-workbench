import json
import tempfile
import unittest
from pathlib import Path

import blender_workbench.sweep as sweep_module
from blender_workbench.recipes.metal_edge_light import (
    MetalEdgeLightSettings,
    coerce_metal_edge_light_settings,
    metal_edge_light_variants,
)
from blender_workbench.sweep import RenderConfig, RenderResult, render_sweep


class MetalEdgeLightTests(unittest.TestCase):
    def test_metal_edge_light_variants_include_failures_and_metadata(self):
        variants = metal_edge_light_variants(prefix="test")

        self.assertEqual(len(variants), 11)
        self.assertEqual(variants[0].name, "test_mirror_edge")
        self.assertGreaterEqual(len([variant for variant in variants if variant.role == "failure_anchor"]), 4)
        satin = next(variant for variant in variants if variant.label == "satin_balanced")
        hot = next(variant for variant in variants if variant.label == "blown_rim_fail")
        matte = next(variant for variant in variants if variant.label == "dead_matte_fail")
        self.assertIn("metal", satin.tags)
        self.assertEqual(satin.settings["material_lighting"]["roughness"], satin.settings["roughness"])
        self.assertGreater(hot.settings["edge_light_strength"], satin.settings["edge_light_strength"])
        self.assertGreater(matte.settings["roughness"], satin.settings["roughness"])

    def test_coerce_settings_ignores_unknown_keys(self):
        settings = coerce_metal_edge_light_settings({"roughness": 0.5, "edge_light_strength": 900.0, "unused": True})

        self.assertIsInstance(settings, MetalEdgeLightSettings)
        self.assertEqual(settings.roughness, 0.5)
        self.assertEqual(settings.edge_light_strength, 900.0)
        self.assertNotIn("unused", settings.__dict__)

    def test_render_sweep_preserves_metal_metadata_without_blender(self):
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
            out_dir = root / "examples/output/metal_edge"
            variants = metal_edge_light_variants(prefix="metal")[:4]
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
                    title="Metal Edge Test",
                )
            finally:
                sweep_module._render_variant = original_render_variant
                sweep_module.write_contact_sheet = original_write_contact_sheet
                sweep_module.write_sweep_diagnostics = original_write_sweep_diagnostics

            metadata = json.loads((out_dir / "metadata.json").read_text())

        self.assertEqual(metadata["variants"][0]["settings"]["material_lighting"]["roughness"], 0.045)
        self.assertEqual(metadata["variants"][2]["settings"]["material_lighting"]["anisotropy"], 0.62)
        self.assertEqual(metadata["workflow"]["pick_handles"][0]["role"], "candidate")


if __name__ == "__main__":
    unittest.main()
