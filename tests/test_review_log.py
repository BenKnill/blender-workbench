import json
import tempfile
import unittest
from pathlib import Path

import blender_workbench.sweep as sweep_module
from blender_workbench.review_log import selected_pick_from_review, write_review_log
from blender_workbench.sweep import RenderConfig, RenderResult, render_selected_from_sweep


def _write_sweep(sweep: Path) -> None:
    sweep.mkdir(parents=True)
    (sweep / "README.md").write_text("# Demo Sweep\n\nRendered variants:\n")
    (sweep / "contact_sheet.png").write_text("image")
    for name in ("wide", "soft", "bad"):
        (sweep / f"{name}.raw.png").write_text("image")
    (sweep / "metadata.json").write_text(
        json.dumps(
            {
                "title": "Demo Sweep",
                "contact_sheet": {"tile": {"width": 88, "height": 88}},
                "workflow": {
                    "pick_handles": [
                        {"index": 1, "name": "wide", "promotion_command": "blender demo.py -- --pick wide"},
                        {"index": 2, "name": "soft", "promotion_command": "blender demo.py -- --pick soft"},
                        {"index": 3, "name": "bad", "promotion_command": "blender demo.py -- --pick bad"},
                    ]
                },
                "variants": [
                    {"name": "wide", "label": "Wide", "raw": str(sweep / "wide.raw.png"), "settings": {"width": 1.4}},
                    {"name": "soft", "label": "Soft", "raw": str(sweep / "soft.raw.png"), "settings": {"width": 1.0}},
                    {"name": "bad", "role": "failure_anchor", "raw": str(sweep / "bad.raw.png"), "settings": {"alpha": 0.9}},
                ],
            }
        )
    )


class ReviewLogTests(unittest.TestCase):
    def test_write_review_log_records_winner_and_updates_readme(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sweep = root / "examples/output/demo"
            _write_sweep(sweep)

            path = write_review_log(
                sweep,
                winner="wide",
                promising=("soft",),
                rejects={"bad": "too opaque"},
                failure_anchors=("bad",),
                tags_by_tile={"soft": ("good_color",)},
                next_note="render wide, then rerun narrower alpha stride",
                reviewer="tester",
                reviewed_at="2026-06-13T00:00:00+00:00",
                root=root,
            )
            review = json.loads(path.read_text())
            readme = (sweep / "README.md").read_text()
            html = (sweep / "review.html").read_text()
            selected_pick = selected_pick_from_review(sweep)

        self.assertEqual(review["winner"], "wide")
        self.assertEqual(review["promotion_pick"], "wide")
        self.assertEqual(review["promotion_command"], "blender demo.py -- --pick wide")
        self.assertEqual(review["promising"], ["soft"])
        self.assertEqual(review["rejects"], [{"name": "bad", "reason": "too opaque"}])
        self.assertEqual(review["next_action"], "render_selected")
        self.assertEqual(selected_pick, "wide")
        self.assertIn("## Visual Review", readme)
        self.assertIn("Winner: `wide`", readme)
        self.assertIn("Next note: render wide, then rerun narrower alpha stride", readme)
        self.assertIn('class="tile candidate reviewed"', html)
        self.assertIn('class="tile failure_anchor reviewed"', html)

    def test_review_log_can_reject_grid_without_winner(self):
        with tempfile.TemporaryDirectory() as tmp:
            sweep = Path(tmp) / "demo"
            _write_sweep(sweep)

            path = write_review_log(
                sweep,
                rejects={"wide": "too subtle", "soft": "wrong direction"},
                next_action="reject_grid",
                next_note="double width stride and change color axis",
            )
            review = json.loads(path.read_text())
            readme = (sweep / "README.md").read_text()
            selected_pick = selected_pick_from_review(sweep)

        self.assertIsNone(review["winner"])
        self.assertEqual(review["next_action"], "reject_grid")
        self.assertIsNone(selected_pick)
        self.assertIn("Winner: none recorded", readme)
        self.assertIn("Next action: `reject_grid`", readme)

    def test_review_log_validates_variant_names_and_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            sweep = Path(tmp) / "demo"
            _write_sweep(sweep)

            with self.assertRaisesRegex(ValueError, "unknown variant"):
                write_review_log(sweep, winner="missing")
            with self.assertRaisesRegex(ValueError, "Unknown review next_action"):
                write_review_log(sweep, winner="wide", next_action="teleport")
            with self.assertRaisesRegex(ValueError, "requires a winner"):
                write_review_log(sweep, next_action="render_selected")

    def test_render_selected_from_sweep_defaults_to_review_winner(self):
        calls = []
        original_render_variant = sweep_module._render_variant

        def fake_render_variant(**kwargs):
            calls.append(kwargs)
            variant = kwargs["variant"]
            return RenderResult(
                name=variant.name,
                raw=None,
                finished=None,
                settings=variant.settings,
                label=variant.label,
                note=variant.note,
                role=variant.role,
                tags=variant.tags,
                render_skipped=True,
                engine=kwargs["config"].engine,
                camera_name=kwargs["config"].camera_name,
            )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sweep = root / "demo"
            _write_sweep(sweep)
            write_review_log(sweep, winner="soft", root=root)
            sweep_module._render_variant = fake_render_variant
            try:
                result = render_selected_from_sweep(
                    sweep_dir=sweep,
                    build_scene=lambda _settings: None,
                    root=root,
                    config=RenderConfig(camera_name="DemoCamera"),
                    postprocess=None,
                    render_image=False,
                    save_blend=True,
                )
            finally:
                sweep_module._render_variant = original_render_variant

        self.assertEqual(result.name, "soft")
        self.assertEqual(calls[0]["variant"].name, "soft")


if __name__ == "__main__":
    unittest.main()
