import json
import tempfile
import unittest
from pathlib import Path

from blender_workbench.example_pick_smoke import (
    format_plan_report,
    pick_smoke_plans,
    plan_pick_smoke,
    safe_output_name,
    script_supports_pick,
    verify_selected_json,
)


class ExamplePickSmokeTests(unittest.TestCase):
    def test_script_supports_pick_detects_promotion_scripts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "example.py"
            script.write_text("parser.add_argument('--pick')\nrender_selected_from_sweep()\n")
            plain = root / "plain.py"
            plain.write_text("print('grid only')\n")

            self.assertTrue(script_supports_pick(script))
            self.assertFalse(script_supports_pick(plain))

    def test_plan_pick_smoke_uses_metadata_variant_and_low_sample_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "examples/output/demo").mkdir(parents=True)
            (root / "examples/demo.py").write_text("parser.add_argument('--pick')\nrender_selected_from_sweep()\n")
            (root / "examples/output/demo/metadata.json").write_text(
                json.dumps(
                    {
                        "variants": [
                            {"name": "wide shell", "label": "wide", "settings": {"width": 1.4}},
                            {"name": "soft_fill", "settings": {"fill": 0.8}},
                        ]
                    }
                )
            )
            example = {
                "name": "demo",
                "script": "examples/demo.py",
                "outputs": ["examples/output/demo/metadata.json"],
            }

            plan = plan_pick_smoke(example, root=root, blender="/bin/blender", hero_samples=3, pick="soft_fill")
            report = format_plan_report([plan])

        self.assertTrue(plan.runnable)
        self.assertEqual(plan.pick, "soft_fill")
        self.assertEqual(plan.command[-5:], ("--", "--pick", "soft_fill", "--hero-samples", "3"))
        self.assertTrue(plan.selected_json.endswith("examples/output/demo/selected/soft_fill/selected.json"))
        self.assertIn("soft_fill", report)

    def test_plan_pick_smoke_blocks_without_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "examples").mkdir()
            (root / "examples/demo.py").write_text("parser.add_argument('--pick')\nrender_selected_from_sweep()\n")
            example = {
                "name": "demo",
                "script": "examples/demo.py",
                "outputs": ["examples/output/demo/metadata.json"],
            }

            plan = plan_pick_smoke(example, root=root)

        self.assertFalse(plan.runnable)
        self.assertIn("metadata.json is missing", plan.reason)

    def test_pick_smoke_plans_filters_to_pick_capable_examples(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "examples/output/pickable").mkdir(parents=True)
            (root / "examples").mkdir(exist_ok=True)
            (root / "examples/pickable.py").write_text("parser.add_argument('--pick')\nrender_selected_from_sweep()\n")
            (root / "examples/plain.py").write_text("print('no pick')\n")
            (root / "examples/output/pickable/metadata.json").write_text(json.dumps({"variants": [{"name": "one", "settings": {}}]}))
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "examples": [
                            {"name": "pickable", "script": "examples/pickable.py", "outputs": ["examples/output/pickable/metadata.json"]},
                            {"name": "plain", "script": "examples/plain.py", "outputs": []},
                        ]
                    }
                )
            )

            plans = pick_smoke_plans(root=root, manifest_path=manifest)

        self.assertEqual([plan.name for plan in plans], ["pickable"])

    def test_verify_selected_json_checks_provenance_and_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = root / "examples/output/demo/selected/one/one.hero.raw.png"
            raw.parent.mkdir(parents=True)
            raw.write_text("image")
            selected_json = raw.parent / "selected.json"
            selected_json.write_text(
                json.dumps(
                    {
                        "source_sweep": "examples/output/demo",
                        "selected": {"name": "one", "settings": {}},
                        "result": {"raw": "examples/output/demo/selected/one/one.hero.raw.png"},
                    }
                )
            )

            errors = verify_selected_json(selected_json, root=root, expected_pick="one")

        self.assertEqual(errors, ())

    def test_safe_output_name_matches_selected_output_folder(self):
        self.assertEqual(safe_output_name("wide shell/hero"), "wide_shell_hero")
        self.assertEqual(safe_output_name("..."), "selected")


if __name__ == "__main__":
    unittest.main()
