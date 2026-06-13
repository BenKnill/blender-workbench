import json
import tempfile
import unittest
from pathlib import Path

import blender_workbench.sweep as sweep_module
from blender_workbench.recipes.procedural_texture import (
    ProceduralTextureSettings,
    coerce_procedural_texture_settings,
    procedural_texture_descriptor,
    procedural_texture_variants,
)
from blender_workbench.sweep import RenderConfig, RenderResult, render_sweep


class ProceduralTextureTests(unittest.TestCase):
    def test_procedural_texture_variants_record_node_descriptors(self):
        variants = procedural_texture_variants(prefix="test", scale_stride=4.0, contrast_stride=0.3, bump_stride=0.1)

        self.assertEqual(len(variants), 11)
        self.assertEqual(variants[0].name, "test_noise_fine_subtle")
        self.assertIn("procedural_texture", variants[0].tags)
        self.assertEqual(variants[-1].role, "failure_anchor")
        fine = variants[0].settings
        marked = next(variant.settings for variant in variants if variant.label == "noise_medium_marked")
        self.assertEqual(fine["node_descriptor"]["node_family"], "noise")
        self.assertEqual(fine["texture_scale"], 72.0)
        self.assertEqual(fine["node_descriptor"]["scale"], fine["texture_scale"])
        self.assertGreater(next(v for v in variants if v.label == "bump_destroyed_fail").settings["bump_strength"], marked["bump_strength"])

    def test_coerce_settings_and_descriptor_ignore_unknown_keys(self):
        settings = coerce_procedural_texture_settings({"node_family": "wave", "texture_scale": 9.5, "unused": True})
        descriptor = procedural_texture_descriptor(settings)

        self.assertIsInstance(settings, ProceduralTextureSettings)
        self.assertEqual(settings.node_family, "wave")
        self.assertEqual(settings.texture_scale, 9.5)
        self.assertNotIn("unused", settings.__dict__)
        self.assertEqual(descriptor["node_family"], "wave")
        self.assertEqual(descriptor["scale"], 9.5)
        self.assertIn("roughness_coupling", descriptor)

    def test_render_sweep_preserves_texture_metadata_without_blender(self):
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
                procedural_controls=kwargs["variant"].procedural_controls,
            )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_dir = root / "examples/output/procedural_texture"
            variants = procedural_texture_variants(prefix="ptex")[:4]
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
                    title="Procedural Texture Test",
                )
            finally:
                sweep_module._render_variant = original_render_variant
                sweep_module.write_contact_sheet = original_write_contact_sheet
                sweep_module.write_sweep_diagnostics = original_write_sweep_diagnostics

            metadata = json.loads((out_dir / "metadata.json").read_text())

        self.assertEqual(metadata["variants"][0]["settings"]["node_descriptor"]["node_family"], "noise")
        self.assertEqual(metadata["variants"][3]["settings"]["node_descriptor"]["node_family"], "wave")
        self.assertEqual(metadata["workflow"]["pick_handles"][0]["role"], "candidate")
        self.assertEqual(metadata["variants"][0]["procedural_controls"]["variation_seed"], 0)


if __name__ == "__main__":
    unittest.main()
