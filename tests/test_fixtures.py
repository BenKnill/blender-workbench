import json
import tempfile
import unittest
from pathlib import Path

import blender_workbench.sweep as sweep_module
from blender_workbench.example_manifest import format_preflight_report, preflight_examples
from blender_workbench.fixtures import fixture_statuses, load_fixture_registry, validate_fixture_registry
from blender_workbench.sweep import RenderConfig, RenderResult, SweepVariant, render_sweep


class FixtureTests(unittest.TestCase):
    def test_real_fixture_registry_loads(self):
        registry = load_fixture_registry(root=Path.cwd())
        names = {fixture["name"] for fixture in registry["fixtures"]}

        self.assertIn("structured_transparency_background", names)
        self.assertIn("studio_tabletop", names)
        self.assertFalse(validate_fixture_registry(registry))

    def test_fixture_status_reports_missing_blend_dependency(self):
        registry = {
            "schema": 1,
            "fixtures": [
                {
                    "name": "external_stage",
                    "kind": "blend_link",
                    "source": "fixtures/missing.blend",
                    "version": 1,
                    "dependencies": ["textures/missing.png"],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmp:
            statuses = fixture_statuses(["external_stage"], registry=registry, root=Path(tmp))

        self.assertFalse(statuses[0].present)
        self.assertEqual(statuses[0].kind, "blend_link")
        self.assertIn("fixtures/missing.blend", statuses[0].missing_dependencies)
        self.assertIn("textures/missing.png", statuses[0].missing_dependencies)

    def test_example_preflight_reports_missing_fixture_separately(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = {
                "examples": [
                    {
                        "name": "fixture_demo",
                        "command": "run fixture demo",
                        "outputs": [],
                        "fixtures": ["missing_fixture"],
                        "prerequisites": [],
                        "cost": {"profile": "shape_scout", "engine": "BLENDER_WORKBENCH", "runtime": "instant"},
                    }
                ]
            }
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest))

            results = preflight_examples(manifest_path=manifest_path, root=root)
            report = format_preflight_report(results)

        self.assertEqual(results[0].status, "blocked_missing_fixture")
        self.assertEqual(results[0].missing_fixtures[0].name, "missing_fixture")
        self.assertIn("missing fixtures: missing_fixture", report)

    def test_render_sweep_records_fixture_provenance_without_blender(self):
        original_render_variant = sweep_module._render_variant
        original_write_contact_sheet = sweep_module.write_contact_sheet

        def fake_render_variant(**kwargs):
            raw = kwargs["out_dir"] / f"{kwargs['variant'].name}.raw.png"
            raw.write_text("image")
            return RenderResult(name=kwargs["variant"].name, raw=str(raw.relative_to(kwargs["root"])), finished=None, settings={})

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry_dir = root / "fixtures"
            registry_dir.mkdir()
            (registry_dir / "registry.json").write_text(
                json.dumps(
                    {
                        "schema": 1,
                        "fixtures": [
                            {
                                "name": "demo_fixture",
                                "kind": "python_builder",
                                "builder": "blender_workbench.fixtures:build_studio_tabletop_fixture",
                                "version": 2,
                                "source": "workbench_python",
                                "expected_objects": ["tabletop"],
                            }
                        ],
                    }
                )
            )
            out_dir = root / "examples/output/demo"
            sweep_module._render_variant = fake_render_variant
            sweep_module.write_contact_sheet = lambda *_args, **_kwargs: None
            try:
                render_sweep(
                    variants=[SweepVariant("wide", {})],
                    build_scene=lambda _settings: None,
                    out_dir=out_dir,
                    root=root,
                    config=RenderConfig(),
                    postprocess=None,
                    fixtures=["demo_fixture"],
                )
            finally:
                sweep_module._render_variant = original_render_variant
                sweep_module.write_contact_sheet = original_write_contact_sheet

            metadata = json.loads((out_dir / "metadata.json").read_text())

        self.assertEqual(metadata["fixtures"][0]["name"], "demo_fixture")
        self.assertEqual(metadata["fixtures"][0]["version"], 2)
        self.assertEqual(metadata["fixtures"][0]["expected_objects"], ["tabletop"])


if __name__ == "__main__":
    unittest.main()
