import json
import tempfile
import unittest
from pathlib import Path

import blender_workbench.sweep as sweep_module
from blender_workbench.recipes.virtual_set_camera import (
    CameraShot,
    VirtualSetSettings,
    virtual_set_camera_shots,
    virtual_set_camera_variants,
)
from blender_workbench.sweep import RenderConfig, RenderResult, render_sweep


class VirtualSetCameraTests(unittest.TestCase):
    def test_virtual_set_camera_variants_record_camera_metadata(self):
        variants = virtual_set_camera_variants(scene_settings=VirtualSetSettings(set_depth=6.2))

        self.assertEqual(len(variants), 6)
        self.assertEqual(variants[0].settings["scene"]["set_depth"], 6.2)
        self.assertEqual(variants[0].settings["camera"]["name"], "wide_establishing")
        self.assertEqual(variants[0].settings["camera"]["lens_mm"], virtual_set_camera_shots()[0].lens_mm)
        self.assertEqual(variants[-1].role, "failure_anchor")
        self.assertEqual(variants[-1].settings["camera"]["name"], "backlight_silhouette_fail")
        self.assertIn("multi_camera", variants[0].tags)

    def test_render_sweep_preserves_camera_metadata_without_blender(self):
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
            out_dir = root / "examples/output/virtual_set"
            variants = virtual_set_camera_variants(
                camera_shots=[
                    CameraShot("wide", "wide", 32.0, 5.5, 0.0, 12.0),
                    CameraShot("bad_back", "bad", 50.0, 4.6, 180.0, 8.0, role="failure_anchor"),
                ]
            )
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
                    title="Virtual Set Test",
                )
            finally:
                sweep_module._render_variant = original_render_variant
                sweep_module.write_contact_sheet = original_write_contact_sheet
                sweep_module.write_sweep_diagnostics = original_write_sweep_diagnostics

            metadata = json.loads((out_dir / "metadata.json").read_text())

        self.assertEqual(metadata["variants"][0]["settings"]["camera"]["name"], "wide")
        self.assertEqual(metadata["variants"][0]["settings"]["camera"]["lens_mm"], 32.0)
        self.assertEqual(metadata["workflow"]["pick_handles"][1]["role"], "failure_anchor")
        self.assertEqual(metadata["variants"][1]["settings"]["camera"]["yaw_degrees"], 180.0)


if __name__ == "__main__":
    unittest.main()
