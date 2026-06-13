import tempfile
import unittest
from pathlib import Path

from tools.pdf_triage import (
    Attempt,
    collect_backend_report,
    default_out_dir,
    try_pdfinfo,
    try_quicklook_thumbnail,
    try_text_extract,
    write_notes_template,
)


class PdfTriageTests(unittest.TestCase):
    def test_collect_backend_report_records_commands_and_python_modules(self):
        report = collect_backend_report(
            which=lambda name: f"/fake/{name}" if name in {"magick", "qlmanage"} else None,
            module_available=lambda name: name == "pypdf",
        )

        self.assertEqual(report["commands"]["magick"]["path"], "/fake/magick")
        self.assertFalse(report["commands"]["pdftotext"]["available"])
        self.assertTrue(report["python_modules"]["pypdf"]["available"])
        self.assertFalse(report["python_modules"]["pdfplumber"]["available"])

    def test_default_out_dir_uses_ignored_runs_folder(self):
        out = default_out_dir(Path("reference/foo bar.pdf"), root=Path("/repo"))

        self.assertEqual(out, Path("/repo/runs/pdf_triage/foo bar"))

    def test_missing_backends_return_skipped_attempts(self):
        report = collect_backend_report(which=lambda _name: None, module_available=lambda _name: False)
        pdf = Path("missing-tool-test.pdf")

        self.assertEqual(try_pdfinfo(pdf, Path("."), report).status, "skipped")
        self.assertEqual(try_text_extract(pdf, Path("."), report, 1, 2).status, "skipped")
        self.assertEqual(try_quicklook_thumbnail(pdf, Path("."), report).status, "skipped")

    def test_write_notes_template_includes_backend_and_attempts(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            report = collect_backend_report(
                which=lambda name: "/usr/bin/qlmanage" if name == "qlmanage" else None,
                module_available=lambda _name: False,
            )
            notes_path = write_notes_template(
                Path("source.pdf"),
                out_dir,
                report,
                [Attempt("thumbnail", "ok", "created Quick Look thumbnail", ("thumb.png",))],
            )
            text = notes_path.read_text()

        self.assertIn("PDF Triage Notes: source.pdf", text)
        self.assertIn("`qlmanage`: /usr/bin/qlmanage", text)
        self.assertIn("thumbnail: ok", text)
        self.assertIn("Candidate sweep axes", text)


if __name__ == "__main__":
    unittest.main()
