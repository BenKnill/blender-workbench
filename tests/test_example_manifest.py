import json
import tempfile
import unittest
from pathlib import Path

from blender_workbench.artifact_fingerprint import make_artifact_fingerprint, write_fingerprint_record
from blender_workbench.example_manifest import (
    format_preflight_report,
    load_manifest,
    normalized_cost,
    normalized_required_capabilities,
    preflight_examples,
    select_examples,
)


class ExampleManifestTests(unittest.TestCase):
    def test_preflight_reports_ready_and_blocked_examples(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs/assets").mkdir(parents=True)
            (root / "docs/assets/ready.jpg").write_text("asset")
            (root / "examples/output/ready").mkdir(parents=True)
            metadata = root / "examples/output/ready/metadata.json"
            metadata.write_text("{}")
            fingerprint = make_artifact_fingerprint("demo", {"name": "ready"})
            write_fingerprint_record(metadata.with_suffix(".fingerprint.json"), fingerprint)
            manifest = {
                "examples": [
                    {
                        "name": "ready",
                        "command": "run ready",
                        "outputs": ["examples/output/ready/metadata.json"],
                        "output_fingerprints": {"examples/output/ready/metadata.json": fingerprint["fingerprint"]},
                        "prerequisites": [],
                        "docs_asset": "docs/assets/ready.jpg",
                        "cost": {
                            "profile": "shape_scout",
                            "engine": "BLENDER_WORKBENCH",
                            "runtime": "instant",
                            "mode": "grid_scout",
                            "requires_blender": True,
                            "tile_count": 1,
                        },
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
                        "cost": {
                            "profile": "cycles_preview",
                            "engine": "CYCLES",
                            "runtime": "quick",
                            "mode": "grid_scout",
                            "requires_blender": True,
                            "tile_count": 9,
                        },
                    },
                ]
            }
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest))

            results = preflight_examples(manifest_path=manifest_path, root=root)
            report = format_preflight_report(results)

        self.assertTrue(results[0].runnable)
        self.assertEqual(results[0].status, "ready")
        self.assertEqual(results[0].outputs_present, ("examples/output/ready/metadata.json",))
        self.assertEqual(results[0].output_statuses["examples/output/ready/metadata.json"], "present_fresh")
        self.assertFalse(results[1].runnable)
        self.assertEqual(results[1].status, "blocked_missing_prereq")
        self.assertEqual(results[1].missing_prerequisites[0]["command"], "run upstream")
        self.assertEqual(results[0].cost["runtime"], "instant")
        self.assertIn("blocked: blocked_missing_prereq", report)
        self.assertIn("cost instant/shape_scout/BLENDER_WORKBENCH/grid_scout/Blender; 1 tiles", report)
        self.assertIn("upstream: run upstream", report)
        self.assertIn("output freshness: present_fresh=1", report)

    def test_preflight_reports_stale_and_unverified_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output_dir = root / "examples/output/demo"
            output_dir.mkdir(parents=True)
            fresh = output_dir / "fresh.json"
            stale = output_dir / "stale.json"
            unverified = output_dir / "unverified.json"
            fresh.write_text("{}")
            stale.write_text("{}")
            unverified.write_text("{}")
            fresh_fingerprint = make_artifact_fingerprint("demo", {"name": "fresh"})
            stale_fingerprint = make_artifact_fingerprint("demo", {"name": "stale-old"})
            expected_stale = make_artifact_fingerprint("demo", {"name": "stale-new"})
            write_fingerprint_record(fresh.with_suffix(".fingerprint.json"), fresh_fingerprint)
            write_fingerprint_record(stale.with_suffix(".fingerprint.json"), stale_fingerprint)
            manifest = {
                "examples": [
                    {
                        "name": "demo",
                        "command": "run demo",
                        "outputs": [
                            "examples/output/demo/fresh.json",
                            "examples/output/demo/stale.json",
                            "examples/output/demo/unverified.json",
                            "examples/output/demo/missing.json",
                        ],
                        "output_fingerprints": {
                            "examples/output/demo/fresh.json": fresh_fingerprint["fingerprint"],
                            "examples/output/demo/stale.json": expected_stale["fingerprint"],
                        },
                        "prerequisites": [],
                        "docs_asset": "docs/assets/missing.jpg",
                        "cost": {"profile": "shape_scout", "engine": "BLENDER_WORKBENCH", "runtime": "instant", "mode": "grid_scout"},
                    }
                ]
            }
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest))

            result = preflight_examples(manifest_path=manifest_path, root=root)[0]

        self.assertEqual(result.output_statuses["examples/output/demo/fresh.json"], "present_fresh")
        self.assertEqual(result.output_statuses["examples/output/demo/stale.json"], "present_stale")
        self.assertEqual(result.output_statuses["examples/output/demo/unverified.json"], "present_unverified")
        self.assertEqual(result.output_statuses["examples/output/demo/missing.json"], "missing")

    def test_preflight_filters_ready_examples_by_cost(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "examples/output/instant").mkdir(parents=True)
            (root / "examples/output/instant/metadata.json").write_text("{}")
            manifest = {
                "examples": [
                    {
                        "name": "instant_ready",
                        "command": "run instant",
                        "outputs": ["examples/output/instant/metadata.json"],
                        "prerequisites": [],
                        "docs_asset": "docs/assets/missing.jpg",
                        "cost": {"profile": "shape_scout", "engine": "BLENDER_WORKBENCH", "runtime": "instant", "mode": "grid_scout"},
                    },
                    {
                        "name": "quick_blocked",
                        "command": "run quick",
                        "outputs": [],
                        "prerequisites": [{"path": "missing/raw.png", "command": "make raw"}],
                        "docs_asset": "docs/assets/missing.jpg",
                        "cost": {"profile": "cycles_preview", "engine": "CYCLES", "runtime": "quick", "mode": "grid_scout"},
                    },
                    {
                        "name": "heavy_ready",
                        "command": "run heavy",
                        "outputs": [],
                        "prerequisites": [],
                        "docs_asset": "docs/assets/missing.jpg",
                        "cost": {"profile": "hero_check", "engine": "CYCLES", "runtime": "heavy", "mode": "selected_render"},
                    },
                ]
            }
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest))

            results = preflight_examples(manifest_path=manifest_path, root=root, ready_only=True, max_cost="quick", sort_by_cost=True)

        self.assertEqual([result.name for result in results], ["instant_ready"])

    def test_preflight_reports_missing_tools_when_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = {
                "examples": [
                    {
                        "name": "tool_blocked",
                        "command": "run tool blocked",
                        "outputs": [],
                        "prerequisites": [],
                        "required_capabilities": ["blender", "magick"],
                        "cost": {"profile": "shape_scout", "engine": "BLENDER_WORKBENCH", "runtime": "instant", "mode": "grid_scout"},
                    }
                ]
            }
            manifest_path = root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest))

            results = preflight_examples(
                manifest_path=manifest_path,
                root=root,
                check_tools=True,
                which=lambda name: f"/fake/{name}" if name == "blender" else None,
                path_exists=lambda _path: False,
            )
            report = format_preflight_report(results)

        self.assertFalse(results[0].runnable)
        self.assertEqual(results[0].status, "blocked_missing_tool")
        self.assertEqual(results[0].required_tools, ("blender", "magick"))
        self.assertEqual(results[0].missing_tools, ("magick",))
        self.assertIn("missing tools: magick", report)

    def test_cost_metadata_validates_runtime_bucket(self):
        self.assertEqual(normalized_cost({"name": "demo", "cost": {"runtime": "quick"}})["runtime"], "quick")
        with self.assertRaisesRegex(ValueError, "Unknown cost bucket"):
            normalized_cost({"name": "demo", "cost": {"runtime": "glacial"}})

    def test_required_capabilities_fall_back_to_cost_when_absent(self):
        self.assertEqual(
            normalized_required_capabilities({"name": "demo", "cost": {"runtime": "quick", "requires_blender": True}}),
            ("blender", "magick"),
        )
        self.assertEqual(
            normalized_required_capabilities(
                {
                    "name": "demo",
                    "cost": {"runtime": "instant", "engine": "PYTHON_IMAGEMAGICK", "requires_blender": False},
                }
            ),
            ("postprocess_only",),
        )

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
            cost = normalized_cost(example)
            self.assertIn(cost["runtime"], {"instant", "quick", "medium", "heavy"})
            self.assertIn("profile", cost)
            self.assertIn("engine", cost)
            self.assertIn("required_capabilities", example)
        postprocess = next(example for example in examples if example["name"] == "postprocess_look_scout")
        self.assertEqual(postprocess["required_capabilities"], ["postprocess_only"])
        self.assertEqual(
            postprocess["prerequisites"][0]["command"],
            "/Applications/Blender.app/Contents/MacOS/Blender --background --python examples/terrain_environment_scout.py -- --pick terrain_relief_p2",
        )

    def test_real_manifest_lists_every_top_level_example_script(self):
        root = Path.cwd()
        examples = load_manifest(root=root)
        manifest_scripts = {example["script"] for example in examples}
        actual_scripts = {str(path.relative_to(root)) for path in (root / "examples").glob("*.py")}

        self.assertEqual(actual_scripts - manifest_scripts, set())


if __name__ == "__main__":
    unittest.main()
