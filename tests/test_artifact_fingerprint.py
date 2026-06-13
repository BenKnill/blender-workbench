import tempfile
import unittest
from pathlib import Path

from blender_workbench.artifact_fingerprint import (
    FRESHNESS_FRESH,
    FRESHNESS_MISSING,
    FRESHNESS_STALE,
    FRESHNESS_UNVERIFIED,
    collect_git_state,
    fingerprint_status,
    make_artifact_fingerprint,
    stable_sha256,
    write_fingerprint_record,
)


class ArtifactFingerprintTests(unittest.TestCase):
    def test_stable_sha_ignores_mapping_order(self):
        self.assertEqual(stable_sha256({"b": 2, "a": 1}), stable_sha256({"a": 1, "b": 2}))

    def test_fingerprint_status_reports_missing_unverified_fresh_and_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "tile.raw.png"
            expected = make_artifact_fingerprint("demo", {"settings": {"width": 1.2}})

            self.assertEqual(fingerprint_status(output, expected["fingerprint"]), FRESHNESS_MISSING)
            output.write_text("image")
            self.assertEqual(fingerprint_status(output, expected["fingerprint"]), FRESHNESS_UNVERIFIED)
            write_fingerprint_record(output.with_suffix(".fingerprint.json"), expected)
            self.assertEqual(fingerprint_status(output, expected["fingerprint"]), FRESHNESS_FRESH)
            other = make_artifact_fingerprint("demo", {"settings": {"width": 1.3}})
            self.assertEqual(fingerprint_status(output, other["fingerprint"]), FRESHNESS_STALE)

    def test_collect_git_state_is_injectable(self):
        calls = []

        def fake_runner(cmd):
            calls.append(cmd)
            if cmd[-1] == "HEAD":
                return True, "abc123"
            return True, " M changed.py"

        state = collect_git_state(Path("/repo"), runner=fake_runner)

        self.assertEqual(state["commit"], "abc123")
        self.assertTrue(state["dirty"])
        self.assertEqual(state["status_short"], " M changed.py")
        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
