import json
import unittest
from pathlib import Path


class SourceTranslationLedgerTests(unittest.TestCase):
    def test_ledger_covers_current_pdf_shelf(self):
        root = Path.cwd()
        ledger = json.loads((root / "docs/source-translation-ledger.json").read_text())
        manifest = json.loads((root / "reference_manifest.json").read_text())

        pdf_ids = {resource["id"] for resource in manifest["resources"] if resource.get("type") == "pdf"}
        entry_source_ids = {entry["source_id"] for entry in ledger["entries"]}

        self.assertEqual(ledger["schema"], 1)
        self.assertTrue(pdf_ids)
        self.assertEqual(pdf_ids - entry_source_ids, set())

    def test_entries_have_required_translation_fields(self):
        root = Path.cwd()
        ledger = json.loads((root / "docs/source-translation-ledger.json").read_text())
        statuses = set(ledger["status_values"])
        required = {
            "id",
            "source_id",
            "source_file",
            "page_range",
            "old_term_or_workflow",
            "modern_concept",
            "prefer_workbench",
            "status",
            "version_notes",
            "related",
        }

        for entry in ledger["entries"]:
            self.assertEqual(required - set(entry), set(), entry["id"])
            self.assertIn(entry["status"], statuses)
            self.assertTrue(entry["old_term_or_workflow"])
            self.assertTrue(entry["modern_concept"])
            self.assertTrue(entry["prefer_workbench"])

    def test_manual_links_point_to_current_blender_docs(self):
        root = Path.cwd()
        ledger = json.loads((root / "docs/source-translation-ledger.json").read_text())
        urls = {link["url"] for link in ledger["manual_links"]}

        self.assertIn("https://docs.blender.org/manual/en/latest/", urls)
        self.assertIn("https://docs.blender.org/manual/en/4.5/", urls)


if __name__ == "__main__":
    unittest.main()
