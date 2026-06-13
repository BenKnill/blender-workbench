import json
import tempfile
import unittest
from pathlib import Path

from blender_workbench.learning_coverage import (
    audit_learning_coverage,
    format_learning_coverage_audit,
    format_learning_coverage_report,
    linked_issue_numbers,
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

    def test_audit_reports_closed_issue_open_rows_and_missing_implemented_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "examples").mkdir()
            (root / "examples/demo.py").write_text("example")
            (root / "docs").mkdir()
            (root / "docs/demo.md").write_text("docs")
            payload = {
                "schema": 1,
                "rows": [
                    {
                        "id": "stale_issue_row",
                        "source_type": "pdf",
                        "source": "source.pdf",
                        "prompt": "prompt",
                        "lesson": "lesson",
                        "status": "issue_open",
                        "links": {"examples": ["examples/demo.py"], "issues": [10, 11], "docs": [], "artifacts": []},
                    },
                    {
                        "id": "open_issue_row",
                        "source_type": "pdf",
                        "source": "source.pdf",
                        "prompt": "prompt",
                        "lesson": "lesson",
                        "status": "issue_open",
                        "links": {"examples": ["examples/demo.py"], "issues": [12], "docs": [], "artifacts": []},
                    },
                    {
                        "id": "missing_path_row",
                        "source_type": "pdf",
                        "source": "source.pdf",
                        "prompt": "prompt",
                        "lesson": "lesson",
                        "status": "implemented",
                        "links": {"examples": ["examples/missing.py"], "issues": [], "docs": ["docs/demo.md"], "artifacts": []},
                    },
                    {
                        "id": "fresh_implemented_row",
                        "source_type": "pdf",
                        "source": "source.pdf",
                        "prompt": "prompt",
                        "lesson": "lesson",
                        "status": "implemented",
                        "links": {"examples": ["examples/demo.py"], "issues": [], "docs": ["docs/demo.md"], "artifacts": []},
                    },
                ],
            }

            findings = audit_learning_coverage(
                payload,
                root=root,
                issue_states={10: "closed", 11: "closed", 12: "open"},
            )
            report = format_learning_coverage_audit(findings)

        self.assertEqual(linked_issue_numbers(payload), (10, 11, 12))
        self.assertEqual(
            [(finding["row_id"], finding["code"]) for finding in findings],
            [
                ("stale_issue_row", "issue_open_all_issues_closed"),
                ("missing_path_row", "implemented_missing_path"),
            ],
        )
        self.assertIn("suggested status: implemented", report)
        self.assertIn("examples/missing.py", report)

    def test_audit_reports_unavailable_issue_state_separately(self):
        payload = {
            "schema": 1,
            "rows": [
                {
                    "id": "missing_issue",
                    "source_type": "pdf",
                    "source": "source.pdf",
                    "prompt": "prompt",
                    "lesson": "lesson",
                    "status": "issue_open",
                    "links": {"examples": [], "issues": [99], "docs": [], "artifacts": []},
                }
            ],
        }

        findings = audit_learning_coverage(payload, check_paths=False, issue_states={99: None})

        self.assertEqual(findings[0]["code"], "issue_lookup_missing")

    def test_load_learning_coverage_rejects_non_object_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "coverage.json"
            path.write_text(json.dumps([]))

            with self.assertRaisesRegex(ValueError, "must contain a JSON object"):
                load_learning_coverage(path)


if __name__ == "__main__":
    unittest.main()
