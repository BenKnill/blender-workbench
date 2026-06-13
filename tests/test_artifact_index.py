import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from blender_workbench.artifact_index import (
    build_artifact_index,
    descriptor_from_metadata,
    format_artifact_report,
    validate_artifact_index,
)


class ArtifactIndexTests(unittest.TestCase):
    def test_workbench_sweep_descriptor_uses_contact_sheet_and_pick_handles(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sweep = root / "examples/output/demo"
            sweep.mkdir(parents=True)
            (sweep / "contact_sheet.png").write_text("image")
            metadata = sweep / "metadata.json"
            metadata.write_text(
                json.dumps(
                    {
                        "title": "Demo Sweep",
                        "render_config": {"engine": "CYCLES", "samples": 32},
                        "workflow": {
                            "stage": "sweep_grid",
                            "status": "needs_selected_render",
                            "pick_handles": [{"name": "wide"}, {"name": "soft"}],
                        },
                        "variants": [
                            {"name": "wide", "raw": "examples/output/demo/wide.raw.png", "settings": {"width": 1.4}}
                        ],
                    }
                )
            )

            descriptor = descriptor_from_metadata(metadata, root=root)
            index = build_artifact_index([root / "examples/output"], root=root)
            report = format_artifact_report(index)

        self.assertIsNotNone(descriptor)
        self.assertEqual(descriptor.artifact_type, "sweep")
        self.assertEqual(descriptor.status, "needs_visual_pick")
        self.assertEqual(descriptor.preview, "examples/output/demo/contact_sheet.png")
        self.assertEqual(descriptor.pick_handles, ("wide", "soft"))
        self.assertEqual(descriptor.render_profile, "CYCLES:32")
        self.assertFalse(validate_artifact_index(index))
        self.assertIn("sweep / needs_visual_pick", report)
        self.assertIn("Demo Sweep", report)

    def test_legacy_variants_metadata_is_adapted_without_rewrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = root / "spacex_vacuum_plume_sweep"
            legacy.mkdir()
            (legacy / "B.finished.png").write_text("image")
            metadata = legacy / "metadata.json"
            metadata.write_text(
                json.dumps(
                    {
                        "variants": [
                            {
                                "name": "B_thin_ghost",
                                "raw": "spacex_vacuum_plume_sweep/B.raw.png",
                                "finished": "spacex_vacuum_plume_sweep/B.finished.png",
                                "settings": {"width": 1.2},
                            }
                        ]
                    }
                )
            )

            descriptor = descriptor_from_metadata(metadata, root=root)

        self.assertEqual(descriptor.artifact_type, "legacy_gallery")
        self.assertEqual(descriptor.preview, "spacex_vacuum_plume_sweep/B.finished.png")
        self.assertEqual(descriptor.pick_handles, ("B_thin_ghost",))
        self.assertIn("legacy variants-only", descriptor.compatibility_notes[0])

    def test_legacy_renders_and_scene_specific_study_are_adapted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gallery = root / "blender_art_exercises"
            gallery.mkdir()
            (gallery / "gobo.finished.png").write_text("image")
            gallery_metadata = gallery / "metadata.json"
            gallery_metadata.write_text(
                json.dumps(
                    {
                        "renders": [
                            {
                                "name": "exercise_01",
                                "finished": "blender_art_exercises/gobo.finished.png",
                                "note": "Dappled light through a physical gobo screen.",
                            }
                        ]
                    }
                )
            )
            study = root / "fast_distinct_lighting_studies_v2/01_dust"
            study.mkdir(parents=True)
            (study / "preview.png").write_text("image")
            study_metadata = study / "metadata.json"
            study_metadata.write_text(
                json.dumps(
                    {
                        "lighting": "Dusty castle silhouette with a single bright low sun blade.",
                        "fighters": [],
                        "resolution": [960, 540],
                    }
                )
            )

            gallery_descriptor = descriptor_from_metadata(gallery_metadata, root=root)
            study_descriptor = descriptor_from_metadata(study_metadata, root=root)

        self.assertEqual(gallery_descriptor.artifact_type, "legacy_gallery")
        self.assertIn("Dappled light", gallery_descriptor.source_cue)
        self.assertEqual(study_descriptor.artifact_type, "reference_study")
        self.assertEqual(study_descriptor.preview, "fast_distinct_lighting_studies_v2/01_dust/preview.png")
        self.assertIn("Dusty castle", study_descriptor.source_cue)

    def test_validate_artifact_index_reports_schema_errors(self):
        errors = validate_artifact_index(
            {"schema_version": 999, "artifacts": [{"id": "", "artifact_type": "mystery", "status": "odd"}]}
        )

        self.assertIn("schema_version must be 1", errors)
        self.assertIn("artifact 1 has unknown artifact_type 'mystery'", errors)
        self.assertIn("artifact 1 has unknown status 'odd'", errors)
        self.assertIn("artifact 1 missing id", errors)
        self.assertIn("artifact 1 missing root", errors)

    def test_cli_validate_reports_missing_index_without_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "artifacts/index.json"

            result = subprocess.run(
                [sys.executable, "tools/artifact_index.py", "validate", "--index", str(missing)],
                capture_output=True,
                text=True,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No ", result.stderr)
        self.assertIn("validate --scan", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_cli_validate_scan_works_without_persisted_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sweep = root / "examples/output/demo"
            sweep.mkdir(parents=True)
            (sweep / "contact_sheet.png").write_text("image")
            (sweep / "metadata.json").write_text(
                json.dumps(
                    {
                        "title": "Demo Sweep",
                        "workflow": {"stage": "sweep_grid", "status": "needs_selected_render"},
                        "variants": [{"name": "wide", "raw": "examples/output/demo/wide.raw.png"}],
                    }
                )
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "tools/artifact_index.py",
                    "validate",
                    "--scan",
                    "--root",
                    str(root),
                    str(root / "examples/output"),
                ],
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("scanned artifact index is valid", result.stdout)


if __name__ == "__main__":
    unittest.main()
