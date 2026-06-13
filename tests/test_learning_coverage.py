import json
import tempfile
import unittest
from pathlib import Path

from blender_workbench.learning_coverage import (
    format_learning_coverage_report,
    load_learning_coverage,
    uncovered_learning_prompts,
    validate_learning_coverage,
)


class LearningCoverageTests(unittest.TestCase):
    def test_validate_reports_schema_and_link_errors(self):
        payload = {
            "schema": 99,
            "rows": [
                {
                    "id": "",
                    "source_type": "pdf",
                    "source": "demo.pdf",
                    "prompt": "prompt",
                    "lesson": "lesson",
                    "status": "mystery",
                    "links": {"examples": "not-a-list"},
                }
            ],
        }

        errors = validate_learning_coverage(payload)

        self.assertIn("schema must be 1", errors)
        self.assertIn("row 1 missing id", errors)
        self.assertIn("row 1 has unknown status 'mystery'", errors)
        self.assertIn("row 1 links.examples must be a list", errors)

    def test_uncovered_report_flags_rows_without_example_or_issue(self):
        payload = {
            "schema": 1,
            "rows": [
                {
                    "id": "covered",
                    "source_type": "pdf",
                    "source": "covered.pdf",
                    "prompt": "covered prompt",
                    "lesson": "covered lesson",
                    "status": "implemented",
                    "links": {"examples": ["examples/demo.py"], "issues": [], "docs": [], "artifacts": []},
                },
                {
                    "id": "uncovered",
                    "source_type": "local_study",
                    "source": "../study",
                    "prompt": "study prompt",
                    "lesson": "study lesson",
                    "status": "needs_exercise",
                    "links": {"examples": [], "issues": [], "docs": ["docs/learning-notes.md"], "artifacts": []},
                },
            ],
        }

        uncovered = uncovered_learning_prompts(payload)
        report = format_learning_coverage_report(payload)

        self.assertEqual([row["id"] for row in uncovered], ["uncovered"])
        self.assertIn("- implemented: 1", report)
        self.assertIn("- needs_exercise: 1", report)
        self.assertIn("uncovered: study prompt", report)

    def test_loads_committed_coverage_without_uncovered_prompts(self):
        coverage = load_learning_coverage(Path("docs/learning-coverage.json"))
        errors = validate_learning_coverage(coverage)

        self.assertFalse(errors)
        self.assertFalse(uncovered_learning_prompts(coverage))
        self.assertGreaterEqual(len(coverage["rows"]), 8)

    def test_load_learning_coverage_rejects_non_object_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "coverage.json"
            path.write_text(json.dumps([]))

            with self.assertRaisesRegex(ValueError, "must contain a JSON object"):
                load_learning_coverage(path)


if __name__ == "__main__":
    unittest.main()
