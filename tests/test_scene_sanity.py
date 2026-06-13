import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import blender_workbench.sweep as sweep_module
from blender_workbench.scene_sanity import (
    SceneSanityExpectations,
    format_scene_sanity_report,
    run_scene_sanity,
    summarize_scene_sanity,
)
from blender_workbench.sweep import RenderConfig, RenderResult, SweepVariant, render_sweep


def _obj(name, obj_type="MESH", *, energy=None, materials=(), scale=(1, 1, 1), rotation=(0, 0, 0)):
    data = SimpleNamespace(materials=[SimpleNamespace(name=material) for material in materials])
    if energy is not None:
        data.energy = energy
    return SimpleNamespace(
        name=name,
        type=obj_type,
        data=data,
        scale=scale,
        rotation_euler=rotation,
        hide_render=False,
        hide_viewport=False,
    )


class SceneSanityTests(unittest.TestCase):
    def test_run_scene_sanity_reports_agent_readable_warnings(self):
        active_camera = _obj("WrongCamera", "CAMERA")
        scene = SimpleNamespace(
            camera=active_camera,
            objects=[
                active_camera,
                _obj("hero subject", materials=("skin material",), scale=(1.4, 1, 1)),
                _obj("key light", "LIGHT", energy=0),
            ],
            render=SimpleNamespace(engine="CYCLES"),
            world=None,
        )

        report = run_scene_sanity(
            scene,
            config=RenderConfig(camera_name="ShotCamera", transparent_max_bounces=4),
            expectations=SceneSanityExpectations(
                expected_camera="ShotCamera",
                expected_objects=("hero subject", "shadow plane"),
                expected_lights=("key light",),
                expected_materials=("skin material", "missing material"),
                require_world=True,
                transparent=True,
                min_transparent_bounces=8,
                warn_unapplied_scale=True,
            ),
        )
        codes = {warning.code for warning in report.warnings}

        self.assertEqual(report.status, "warning")
        self.assertTrue(report.passed)
        self.assertIn("missing_camera", codes)
        self.assertIn("active_camera_mismatch", codes)
        self.assertIn("missing_world", codes)
        self.assertIn("missing_object", codes)
        self.assertIn("zero_energy_light", codes)
        self.assertIn("missing_material", codes)
        self.assertIn("low_transparent_bounces", codes)
        self.assertIn("unapplied_scale", codes)
        self.assertIn("missing_camera", format_scene_sanity_report(report))

    def test_run_scene_sanity_strict_fails_on_warnings(self):
        scene = SimpleNamespace(
            camera=None,
            objects=[],
            render=SimpleNamespace(engine="BLENDER_WORKBENCH"),
            world=SimpleNamespace(name="world"),
        )

        report = run_scene_sanity(
            scene,
            config=RenderConfig.shape_scout(),
            expectations={"min_subject_objects": 1},
            strict=True,
        )

        self.assertEqual(report.status, "failed")
        self.assertFalse(report.passed)
        self.assertIn("empty_or_tiny_scene", {warning.code for warning in report.warnings})

    def test_summarize_scene_sanity_deduplicates_warnings(self):
        report = {
            "status": "warning",
            "strict": False,
            "strict_passed": False,
            "warnings": [
                {"code": "missing_camera", "subject": "ShotCamera", "message": "missing"},
                {"code": "missing_camera", "subject": "ShotCamera", "message": "missing"},
            ],
        }

        summary = summarize_scene_sanity([report])

        self.assertEqual(summary["status"], "warning")
        self.assertTrue(summary["passed"])
        self.assertEqual(len(summary["warnings"]), 1)

    def test_render_sweep_records_scene_sanity_metadata_without_blender(self):
        calls = []
        original_render_variant = sweep_module._render_variant
        original_write_contact_sheet = sweep_module.write_contact_sheet
        original_write_sweep_diagnostics = sweep_module.write_sweep_diagnostics
        expectations = {"expected_camera": "DemoCamera"}

        def fake_render_variant(**kwargs):
            calls.append(kwargs)
            raw = kwargs["out_dir"] / f"{kwargs['variant'].name}.raw.png"
            raw.write_text("image")
            return RenderResult(
                name=kwargs["variant"].name,
                raw=str(raw.relative_to(kwargs["root"])),
                finished=None,
                settings=kwargs["variant"].settings,
                scene_sanity={
                    "status": "warning",
                    "strict": False,
                    "passed": True,
                    "strict_passed": False,
                    "warnings": [
                        {
                            "code": "missing_camera",
                            "message": "Expected camera 'DemoCamera' was not found",
                            "subject": "DemoCamera",
                            "severity": "warning",
                        }
                    ],
                    "render_config": {"engine": "CYCLES", "camera_name": "DemoCamera"},
                },
            )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_dir = root / "examples/output/demo"
            sweep_module._render_variant = fake_render_variant
            sweep_module.write_contact_sheet = lambda *_args, **_kwargs: None
            sweep_module.write_sweep_diagnostics = lambda *_args, **_kwargs: {"warnings": []}
            try:
                render_sweep(
                    variants=[SweepVariant("wide", {"width": 1.4})],
                    build_scene=lambda _settings: None,
                    out_dir=out_dir,
                    root=root,
                    config=RenderConfig(camera_name="DemoCamera"),
                    postprocess=None,
                    scene_expectations=expectations,
                    strict_scene_sanity=False,
                )
            finally:
                sweep_module._render_variant = original_render_variant
                sweep_module.write_contact_sheet = original_write_contact_sheet
                sweep_module.write_sweep_diagnostics = original_write_sweep_diagnostics

            metadata = json.loads((out_dir / "metadata.json").read_text())
            readme = (out_dir / "README.md").read_text()

        self.assertEqual(calls[0]["scene_expectations"], expectations)
        self.assertFalse(calls[0]["strict_scene_sanity"])
        self.assertEqual(metadata["scene_sanity"]["status"], "warning")
        self.assertTrue(metadata["scene_sanity"]["passed"])
        self.assertEqual(metadata["scene_sanity"]["warnings"][0]["code"], "missing_camera")
        self.assertEqual(metadata["variants"][0]["scene_sanity"]["warnings"][0]["subject"], "DemoCamera")
        self.assertIn("Scene sanity", readme)


if __name__ == "__main__":
    unittest.main()
