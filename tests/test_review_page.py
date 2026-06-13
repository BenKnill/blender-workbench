import json
import tempfile
import unittest
from pathlib import Path

from blender_workbench.review_page import render_review_html, write_review_page


class ReviewPageTests(unittest.TestCase):
    def test_write_review_page_links_contact_sheet_tiles_and_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sweep = root / "examples/output/demo"
            sweep.mkdir(parents=True)
            for name in ("contact_sheet.png", "wide.raw.png", "wide.finished.png", "fail.raw.png"):
                (sweep / name).write_text("image")
            (sweep / "review.json").write_text(json.dumps({"reviewed": ["wide"]}))
            metadata = {
                "title": "Demo Sweep",
                "contact_sheet": {"tile": {"width": 88, "height": 88}},
                "workflow": {
                    "pick_handles": [
                        {"name": "wide", "promotion_command": "blender --background --python demo.py -- --pick wide"}
                    ]
                },
                "variants": [
                    {
                        "name": "wide",
                        "label": "Wide Shell",
                        "note": "best thumbnail",
                        "role": "candidate",
                        "tags": ["keeper"],
                        "raw": "examples/output/demo/wide.raw.png",
                        "finished": "examples/output/demo/wide.finished.png",
                        "settings": {"width": 1.4, "alpha": 0.05},
                    },
                    {
                        "name": "fail",
                        "role": "failure_anchor",
                        "raw": "examples/output/demo/fail.raw.png",
                        "settings": {"alpha": 0.8},
                    },
                ],
            }
            (sweep / "metadata.json").write_text(json.dumps(metadata))

            path = write_review_page(sweep, root=root)
            text = path.read_text()

        self.assertIn("Demo Sweep", text)
        self.assertIn('href="contact_sheet.png"', text)
        self.assertIn('class="tile candidate reviewed"', text)
        self.assertIn('class="tile failure_anchor"', text)
        self.assertIn('href="wide.raw.png"', text)
        self.assertIn('href="wide.finished.png"', text)
        self.assertIn("best thumbnail", text)
        self.assertIn("width=1.4", text)
        self.assertIn("data-command=\"blender --background --python demo.py -- --pick wide\"", text)

    def test_render_review_html_escapes_metadata_text(self):
        html = render_review_html(
            {
                "title": "<Demo>",
                "variants": [
                    {
                        "name": "bad<script>",
                        "note": "<unsafe>",
                        "raw": "tile.png",
                        "settings": {"text": "<tag>"},
                    }
                ],
            },
            base=Path("."),
            root=Path("."),
        )

        self.assertIn("&lt;Demo&gt;", html)
        self.assertIn("bad&lt;script&gt;", html)
        self.assertIn("&lt;unsafe&gt;", html)
        self.assertNotIn("<unsafe>", html)


if __name__ == "__main__":
    unittest.main()
