import unittest
from pathlib import Path

from blender_workbench.capabilities import (
    collect_capability_report,
    expand_required_tools,
    format_capability_report,
    resolve_tool_path,
)


class CapabilityTests(unittest.TestCase):
    def test_expand_required_tools_supports_feature_groups(self):
        self.assertEqual(expand_required_tools(["blender", "magick"]), ("blender", "magick"))
        self.assertEqual(expand_required_tools(["postprocess_only"]), ("python3", "magick"))
        self.assertEqual(expand_required_tools(["video_reference"]), ("ffmpeg", "yt-dlp"))

    def test_resolve_blender_prefers_app_bundle_path(self):
        path = resolve_tool_path(
            "blender",
            which=lambda _name: "/fake/path/blender",
            path_exists=lambda path: path == Path("/Applications/Blender.app/Contents/MacOS/Blender"),
        )

        self.assertEqual(path, "/Applications/Blender.app/Contents/MacOS/Blender")

    def test_collect_capability_report_records_missing_tools_and_versions(self):
        available = {
            "python3",
            "blender",
            "magick",
            "ffmpeg",
            "swift",
            "qlmanage",
        }

        def fake_which(name):
            return f"/fake/{name}" if name in available else None

        def fake_runner(cmd):
            return True, f"{Path(cmd[0]).name} version"

        report = collect_capability_report(
            which=fake_which,
            path_exists=lambda _path: False,
            runner=fake_runner,
            module_available=lambda name: name == "blender_workbench",
        )
        text = format_capability_report(report)

        self.assertEqual(report["commands"]["blender"]["version"], "blender version")
        self.assertEqual(report["capability_groups"]["blender"]["status"], "ready")
        self.assertEqual(report["capability_groups"]["video_reference"]["status"], "blocked_missing_tool")
        self.assertEqual(report["capability_groups"]["video_reference"]["missing_tools"], ("yt-dlp",))
        self.assertEqual(report["capability_groups"]["pdf_triage"]["status"], "ready")
        self.assertIn("video_reference: blocked_missing_tool", text)
        self.assertIn("missing tools: yt-dlp", text)


if __name__ == "__main__":
    unittest.main()
