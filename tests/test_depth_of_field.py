import json
import tempfile
import unittest
from pathlib import Path

import blender_workbench.sweep as sweep_module
from blender_workbench.recipes.depth_of_field import (
    DepthOfFieldSettings,
    coerce_depth_of_field_settings,
    depth_of_field_descriptor,
    depth_of_field_variants,
    focus_plane_targets,
)
from blender_workbench.sweep import RenderConfig, RenderResult, render_sweep


class DepthOfFieldTests(unittest.TestCase):
    def test_depth_of_field_variants_record_focus_planes_and_failures(self):
        variants = depth_of_field_variants(prefix="test")

        self.assertEqual(len(variants), 11)
        self.assertEqual(variants[0].name, "test_subject_moderate")
        self.assertEqual(variants[0].role, "baseline")
        self.assertIn("depth_of_field", variants[0].tags)
        self.assertEqual(variants[0].settings["focus_diagnostics"]["focus_plane"], "subject")
        focus_planes = {variant.settings["focus_diagnostics"]["focus_plane"] for variant in variants}
        self.assertEqual(focus_planes, {"foreground", "subject", "background"})
        failures = [variant for variant in variants if variant.role == "failure_anchor"]
        self.assertEqual({variant.label for variant in failures}, {"all_sharp_fail", "wrong_plane_fail", "over_blurred_fail"})

        all_sharp = next(variant for variant in variants if variant.label == "all_sharp_fail")
        over_blurred = next(variant for variant in variants if variant.label == "over_blurred_fail")
        tele = next(variant for variant in variants if variant.label == "tele_bokeh")
        self.assertGreater(all_sharp.settings["focus_diagnostics"]["aperture_fstop"], variants[0].settings["focus_diagnostics"]["aperture_fstop"])
        self.assertLess(over_blurred.settings["focus_diagnostics"]["aperture_fstop"], variants[0].settings["focus_diagnostics"]["aperture_fstop"])
        self.assertGreater(tele.settings["focus_diagnostics"]["camera_lens"], variants[0].settings["focus_diagnostics"]["camera_lens"])

    def test_coerce_settings_descriptor_and_focus_targets_ignore_unknown_keys(self):
        settings = coerce_depth_of_field_settings({"focus_plane": "background", "aperture_fstop": 1.8, "unused": True})
        descriptor = depth_of_field_descriptor(settings)
        targets = focus_plane_targets(settings)

        self.assertIsInstance(settings, DepthOfFieldSettings)
        self.assertEqual(settings.focus_plane, "background")
        self.assertEqual(settings.aperture_fstop, 1.8)
        self.assertNotIn("unused", settings.__dict__)
        self.assertEqual(descriptor["available_focus_planes"], ("foreground", "subject", "background"))
        self.assertEqual(descriptor["focus_plane"], "background")
        self.assertLess(targets["foreground"][1], targets["subject"][1])
        self.assertLess(targets["subject"][1], targets["background"][1])

    def test_render_sweep_preserves_focus_metadata_without_blender(self):
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
            out_dir = root / "examples/output/depth_of_field"
            variants = depth_of_field_variants(prefix="dof")[:4]
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
                    title="Depth Of Field Test",
                )
            finally:
                sweep_module._render_variant = original_render_variant
                sweep_module.write_contact_sheet = original_write_contact_sheet
                sweep_module.write_sweep_diagnostics = original_write_sweep_diagnostics

            metadata = json.loads((out_dir / "metadata.json").read_text())

        self.assertEqual(metadata["variants"][0]["settings"]["focus_diagnostics"]["technique"], "camera_depth_of_field")
        self.assertEqual(metadata["variants"][0]["settings"]["focus_diagnostics"]["diagnostics"][0], "foreground_slats")
        self.assertEqual(metadata["workflow"]["pick_handles"][0]["role"], "baseline")
        self.assertEqual(metadata["variants"][3]["settings"]["focus_diagnostics"]["focus_plane"], "background")


if __name__ == "__main__":
    unittest.main()
