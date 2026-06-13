import json
import tempfile
import unittest
from pathlib import Path

from tools.pdf_lesson_index import (
    build_lesson_index,
    format_queue_report,
    import_toc_ranges,
    mark_range,
    next_items,
    parse_pages,
    parse_toc_entry,
    read_page_count_mdls,
)


class PdfLessonIndexTests(unittest.TestCase):
    def test_read_page_count_mdls_parses_raw_count(self):
        count = read_page_count_mdls(Path("demo.pdf"), runner=lambda _cmd: (True, "42"))

        self.assertEqual(count, 42)
        self.assertIsNone(read_page_count_mdls(Path("demo.pdf"), runner=lambda _cmd: (True, "(null)")))

    def test_build_index_uses_reference_manifest_and_preserves_ranges(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pdf_dir = root / "reference"
            pdf_dir.mkdir()
            (pdf_dir / "lesson_lighting.pdf").write_text("pdf")
            (pdf_dir / "lesson_texture.pdf").write_text("pdf")
            manifest = {
                "schema": 1,
                "resources": [
                    {
                        "id": "lesson_lighting",
                        "type": "pdf",
                        "path": "reference/lesson_lighting.pdf",
                        "source_url": "https://example.test/lighting",
                        "sha256": "abc",
                    }
                ],
            }
            manifest_path = root / "reference_manifest.json"
            manifest_path.write_text(json.dumps(manifest))
            existing = {
                "schema": 1,
                "sources": [
                    {
                        "source_id": "lesson_lighting",
                        "title": "Lighting Lesson",
                        "status": "candidate",
                        "priority": 91,
                        "tags": ["lighting"],
                        "ranges": [{"pages": "4-6", "status": "candidate", "tags": ["exercise"]}],
                    }
                ],
            }

            index = build_lesson_index(
                pdf_dir,
                root=root,
                existing=existing,
                reference_manifest=manifest_path,
                page_count_reader=lambda path: 12 if path.name == "lesson_lighting.pdf" else 9,
            )

        lighting = next(source for source in index["sources"] if source["source_id"] == "lesson_lighting")
        texture = next(source for source in index["sources"] if source["source_id"] == "lesson_texture")
        self.assertEqual(lighting["page_count"], 12)
        self.assertEqual(lighting["status"], "candidate")
        self.assertEqual(lighting["ranges"][0]["pages"], "4-6")
        self.assertEqual(lighting["source_url"], "https://example.test/lighting")
        self.assertEqual(texture["page_count"], 9)
        self.assertEqual(texture["status"], "unskimmed")

    def test_next_queue_prefers_candidate_ranges_then_priority(self):
        index = {
            "schema": 1,
            "sources": [
                {
                    "source_id": "low_priority_candidate",
                    "title": "Low",
                    "path": "low.pdf",
                    "page_count": 50,
                    "status": "unskimmed",
                    "priority": 10,
                    "tags": ["lighting"],
                    "ranges": [{"pages": "20-22", "status": "candidate", "tags": ["exercise"]}],
                },
                {
                    "source_id": "high_priority_unskimmed",
                    "title": "High",
                    "path": "high.pdf",
                    "page_count": 20,
                    "status": "unskimmed",
                    "priority": 95,
                    "tags": ["compositing"],
                    "ranges": [],
                },
            ],
        }

        items = next_items(index, limit=2)
        report = format_queue_report(items)

        self.assertEqual(items[0]["source_id"], "low_priority_candidate")
        self.assertEqual(items[0]["pages"], "20-22")
        self.assertEqual(items[1]["pages"], "1-8")
        self.assertIn("triage: python3 tools/pdf_triage.py low.pdf --first-page 20 --last-page 22", report)

    def test_mark_range_updates_links_and_status(self):
        index = {
            "schema": 1,
            "updated": "old",
            "sources": [
                {
                    "source_id": "lesson_lighting",
                    "title": "Lighting",
                    "path": "lighting.pdf",
                    "page_count": 20,
                    "status": "unskimmed",
                    "priority": 90,
                    "tags": [],
                    "ranges": [],
                }
            ],
        }

        entry = mark_range(
            index,
            source_id="lesson",
            pages="12-15",
            status="issue_open",
            tags=["lighting", "exercise"],
            issue=54,
            triage_output="runs/pdf_triage/lighting",
            coverage_entry="coverage:lighting",
            example="examples/light_texture_scout.py",
            note="strong light exercise",
        )

        self.assertEqual(entry["pages"], "12-15")
        self.assertEqual(entry["status"], "issue_open")
        self.assertEqual(entry["issue"], 54)
        self.assertEqual(entry["triage_output"], "runs/pdf_triage/lighting")
        self.assertEqual(index["sources"][0]["status"], "issue_open")

    def test_import_toc_ranges_adds_titles_and_prioritized_candidates(self):
        index = {
            "schema": 1,
            "updated": "old",
            "sources": [
                {
                    "source_id": "lesson_lighting",
                    "title": "Lighting",
                    "path": "lighting.pdf",
                    "page_count": 30,
                    "status": "unskimmed",
                    "priority": 90,
                    "tags": ["lighting"],
                    "ranges": [],
                },
                {
                    "source_id": "plain_unskimmed",
                    "title": "Plain",
                    "path": "plain.pdf",
                    "page_count": 12,
                    "status": "unskimmed",
                    "priority": 99,
                    "tags": [],
                    "ranges": [],
                },
            ],
        }

        entries = import_toc_ranges(
            index,
            source_id="lesson",
            entries=[
                "5-6=Fun with Shadows:shadow,lighting",
                "10-11=Mesh Lights:mesh_light,lighting",
            ],
            tags=["toc"],
            priority=97,
            triage_output="runs/pdf_triage/lesson_lighting",
        )
        items = next_items(index, limit=3)
        report = format_queue_report(items)

        self.assertEqual(entries[0]["title"], "Fun with Shadows")
        self.assertEqual(entries[0]["priority"], 97)
        self.assertEqual(entries[0]["triage_output"], "runs/pdf_triage/lesson_lighting")
        self.assertEqual(index["sources"][0]["status"], "candidate")
        self.assertEqual(items[0]["source_id"], "lesson_lighting")
        self.assertEqual(items[0]["range_title"], "Fun with Shadows")
        self.assertEqual(items[0]["priority"], 97)
        self.assertIn("toc", items[0]["tags"])
        self.assertEqual(items[2]["source_id"], "plain_unskimmed")
        self.assertIn("Fun with Shadows", report)

    def test_parse_pages_rejects_reversed_ranges(self):
        self.assertEqual(parse_pages("3"), (3, 3))
        with self.assertRaisesRegex(ValueError, "Invalid page range"):
            parse_pages("9-2")

    def test_parse_toc_entry_rejects_missing_title_separator(self):
        self.assertEqual(
            parse_toc_entry("10-11=Mesh Lights:mesh_light,lighting"),
            {"pages": "10-11", "title": "Mesh Lights", "tags": ["mesh_light", "lighting"]},
        )
        with self.assertRaisesRegex(ValueError, "TOC entry must use"):
            parse_toc_entry("10-11 Mesh Lights")


if __name__ == "__main__":
    unittest.main()
