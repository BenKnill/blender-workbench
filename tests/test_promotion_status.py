import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from blender_workbench.promotion_status import classify_sweep, format_promotion_report, main, promotion_statuses


def write_sweep(root: Path, name: str, workflow: dict | None = None) -> Path:
    sweep_dir = root / "examples/output" / name
    sweep_dir.mkdir(parents=True)
    (sweep_dir / "contact_sheet.png").write_text("sheet")
    (sweep_dir / "README.md").write_text("readme")
    payload = {
        "workflow": workflow
        or {
            "stage": "sweep_grid",
            "status": "needs_selected_render",
            "pick_handles": [
                {
                    "index": 1,
                    "name": "wide_shell",
                    "label": "wide",
                }
            ],
            "promotion_command_template": "blender --background --python examples/demo.py -- --pick {pick}",
        },
        "variants": [{"name": "wide_shell", "settings": {"width": 1.4}}],
    }
    (sweep_dir / "metadata.json").write_text(json.dumps(payload))
    return sweep_dir


class PromotionStatusTests(unittest.TestCase):
    def test_unpromoted_sweep_reports_pick_handles_and_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sweep_dir = write_sweep(root, "demo")

            status = classify_sweep(sweep_dir / "metadata.json", root=root)
            report = format_promotion_report([status])

        self.assertEqual(status.status, "needs_visual_pick")
        self.assertEqual(status.contact_sheet, "examples/output/demo/contact_sheet.png")
        self.assertEqual(status.readme, "examples/output/demo/README.md")
        self.assertEqual(status.pick_handles[0]["name"], "wide_shell")
        self.assertIn("--pick wide_shell", status.promotion_commands[0])
        self.assertIn("needs_visual_pick", report)
        self.assertIn("promote: blender", report)

    def test_selected_render_with_matching_provenance_is_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sweep_dir = write_sweep(root, "demo")
            selected_dir = sweep_dir / "selected/wide_shell"
            selected_dir.mkdir(parents=True)
            (selected_dir / "selected.json").write_text(
                json.dumps(
                    {
                        "source_sweep": "examples/output/demo",
                        "selected": {"name": "wide_shell", "settings": {}},
                    }
                )
            )

            status = classify_sweep(sweep_dir / "metadata.json", root=root)

        self.assertEqual(status.status, "selected_render_complete")
        self.assertEqual(status.selected_json, "examples/output/demo/selected/wide_shell/selected.json")
        self.assertEqual(status.pick, "wide_shell")

    def test_explicit_rejected_grid_is_not_required_for_promotion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sweep_dir = write_sweep(
                root,
                "demo",
                {
                    "stage": "sweep_grid",
                    "status": "rejected_grid",
                    "rejection_note": "all tiles were too timid; widen alpha stride",
                    "pick_handles": [{"index": 1, "name": "flat"}],
                },
            )

            status = classify_sweep(sweep_dir / "metadata.json", root=root)

        self.assertEqual(status.status, "rejected_grid")
        self.assertIn("too timid", status.detail)

    def test_stale_selected_render_reports_ambiguous_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sweep_dir = write_sweep(root, "demo")
            selected_dir = sweep_dir / "selected/wide_shell"
            selected_dir.mkdir(parents=True)
            (selected_dir / "selected.json").write_text(
                json.dumps(
                    {
                        "source_sweep": "examples/output/other",
                        "selected": {"name": "wide_shell", "settings": {}},
                    }
                )
            )

            status = classify_sweep(sweep_dir / "metadata.json", root=root)

        self.assertEqual(status.status, "stale_or_ambiguous")
        self.assertIn("provenance did not match", status.detail)
        self.assertTrue(status.promotion_commands)

    def test_promotion_statuses_scan_roots_and_skip_non_sweeps(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_sweep(root, "demo")
            look_dir = root / "examples/output/look"
            look_dir.mkdir(parents=True)
            (look_dir / "metadata.json").write_text(json.dumps({"mode": "postprocess_sweep", "variants": []}))

            results = promotion_statuses([Path("examples/output")], root=root)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].sweep_dir, "examples/output/demo")

    def test_require_promoted_exits_nonzero_for_unpromoted_grids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_sweep(root, "demo")

            with self.assertRaises(SystemExit):
                with redirect_stdout(StringIO()):
                    main(["--root", str(root), "--require-promoted", "examples/output"])


if __name__ == "__main__":
    unittest.main()
