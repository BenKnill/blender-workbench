import json
import tempfile
import unittest
from pathlib import Path

from blender_workbench.example_manifest import format_preflight_report, load_manifest, preflight_examples, select_examples


class ExampleManifestTests(unittest.TestCase):
    def test_preflight_reports_ready_and_blocked_examples(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs/assets").mkdir(parents=True)
            (root / "docs/assets/ready.jpg").write_text("asset")
            (root / "examples/output/ready").mkdir(parents=True)
            (root / "examples/output/ready/metadata.json").write_text("{}")
            manifest = {
                "examples": [
                    {
                        "name": "ready",
                        "command": "run ready",
                        "outputs": ["examples/output/ready/metadata.json"],
                        "prerequisites": [],
                        "docs_asset": "docs/assets/ready.jpg",
                    },
                    {
                        "name": "blocked",
                        "command": "run blocked",
                        "outputs": ["examples/output/blocked/metadata.json"],
                        "prerequisites": [
                            {
                                "path": "examples/output/upstream/raw.png",
                                "command": "run upstream",
                                "note": "needed raw image",
                            }
                        ],
                        "docs_asset": "docs/assets/missing.jpg",
                    },
                ]
            }
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest))

            results = preflight_examples(manifest_path=manifest_path, root=root)
            report = format_preflight_report(results)

        self.assertTrue(results[0].runnable)
        self.assertEqual(results[0].outputs_present, ("examples/output/ready/metadata.json",))
        self.assertFalse(results[1].runnable)
        self.assertEqual(results[1].missing_prerequisites[0]["command"], "run upstream")
        self.assertIn("blocked: blocked", report)
        self.assertIn("upstream: run upstream", report)

    def test_select_examples_rejects_unknown_names(self):
        examples = [{"name": "one"}, {"name": "two"}]

        self.assertEqual(select_examples(examples, ["two"]), [{"name": "two"}])
        with self.assertRaisesRegex(ValueError, "Unknown example"):
            select_examples(examples, ["missing"])

    def test_real_manifest_points_to_existing_scripts_and_docs_assets(self):
        root = Path.cwd()
        examples = load_manifest(root=root)
        names = {example["name"] for example in examples}

        self.assertIn("postprocess_look_scout", names)
        for example in examples:
            self.assertTrue((root / example["script"]).exists(), example["script"])
            self.assertTrue((root / example["docs_asset"]).exists(), example["docs_asset"])
        postprocess = next(example for example in examples if example["name"] == "postprocess_look_scout")
        self.assertEqual(
            postprocess["prerequisites"][0]["command"],
            "/Applications/Blender.app/Contents/MacOS/Blender --background --python examples/terrain_environment_scout.py -- --pick terrain_relief_p2",
        )


if __name__ == "__main__":
    unittest.main()
