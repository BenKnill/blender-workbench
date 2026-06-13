import json
import tempfile
import unittest
from pathlib import Path

from tools.reference_manifest import (
    directory_fingerprint,
    format_status_report,
    load_manifest,
    sha256_file,
    verify_manifest,
    verify_resource,
)


class ReferenceManifestTests(unittest.TestCase):
    def test_verify_file_resource_checks_size_and_sha(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resource_path = root / "refs/source.txt"
            resource_path.parent.mkdir()
            resource_path.write_text("reference")
            resource = {
                "id": "source",
                "type": "pdf",
                "path": "refs/source.txt",
                "size_bytes": resource_path.stat().st_size,
                "sha256": sha256_file(resource_path),
            }

            result = verify_resource(resource, root=root)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.detail, "file fingerprint matches")

    def test_verify_directory_resource_checks_aggregate_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            frames = root / "refs/frames"
            frames.mkdir(parents=True)
            (frames / "frame_001.jpg").write_text("one")
            (frames / "frame_002.jpg").write_text("two")
            count, total_size, digest = directory_fingerprint(frames)
            resource = {
                "id": "frames",
                "type": "frame_sequence",
                "path": "refs/frames",
                "file_count": count,
                "total_size_bytes": total_size,
                "aggregate_sha256": digest,
            }

            result = verify_resource(resource, root=root)

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.actual_file_count, 2)
        self.assertEqual(result.detail, "directory fingerprint matches")

    def test_verify_manifest_reports_missing_and_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            present = root / "present.txt"
            present.write_text("changed")
            manifest = {
                "schema": 1,
                "resources": [
                    {
                        "id": "present",
                        "type": "pdf",
                        "path": "present.txt",
                        "size_bytes": 999,
                        "sha256": sha256_file(present),
                    },
                    {
                        "id": "missing",
                        "type": "pdf",
                        "path": "missing.pdf",
                        "size_bytes": 12,
                        "sha256": "abc",
                    },
                ],
            }
            manifest_path = root / "reference_manifest.json"
            manifest_path.write_text(json.dumps(manifest))

            results = verify_manifest(manifest_path, root=root)
            report = format_status_report(results)

        self.assertEqual([result.status for result in results], ["mismatch", "missing"])
        self.assertIn("present: mismatch", report)
        self.assertIn("missing: missing", report)

    def test_real_manifest_schema_loads(self):
        manifest = load_manifest(Path("reference_manifest.json"), root=Path.cwd())

        self.assertGreaterEqual(len(manifest["resources"]), 10)
        self.assertTrue(any(resource["id"] == "saocom_frames" for resource in manifest["resources"]))


if __name__ == "__main__":
    unittest.main()
