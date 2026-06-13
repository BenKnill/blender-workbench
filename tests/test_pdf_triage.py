import tempfile
import unittest
from pathlib import Path

from tools.pdf_triage import (
    Attempt,
    collect_backend_report,
    default_out_dir,
    swift_pdf_renderer_source,
    try_native_macos_page_render,
    try_page_contact_sheet,
    try_pdfinfo,
    try_quicklook_thumbnail,
    try_text_extract,
    write_notes_template,
)


class PdfTriageTests(unittest.TestCase):
    def test_collect_backend_report_records_commands_and_python_modules(self):
        report = collect_backend_report(
            which=lambda name: f"/fake/{name}" if name in {"magick", "qlmanage", "swift"} else None,
            module_available=lambda name: name == "pypdf",
        )

        self.assertEqual(report["commands"]["magick"]["path"], "/fake/magick")
        self.assertEqual(report["commands"]["swift"]["path"], "/fake/swift")
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
        self.assertEqual(try_native_macos_page_render(pdf, Path("."), report, 1, 2, platform="darwin").status, "skipped")
        self.assertEqual(try_page_contact_sheet(Attempt("page_render", "skipped", "none"), Path("."), report).status, "skipped")

    def test_native_macos_page_render_backend_records_page_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            report = collect_backend_report(
                which=lambda name: "/usr/bin/swift" if name == "swift" else None,
                module_available=lambda _name: False,
            )

            def fake_swift(cmd):
                pages_dir = Path(cmd[3])
                pages_dir.mkdir(parents=True)
                (pages_dir / "page-0002.png").write_text("page 2")
                (pages_dir / "page-0003.png").write_text("page 3")
                return True, "rendered"

            attempt = try_native_macos_page_render(
                Path("source.pdf"),
                out_dir,
                report,
                2,
                3,
                run=fake_swift,
                platform="darwin",
            )

        self.assertEqual(attempt.name, "page_render")
        self.assertEqual(attempt.status, "ok")
        self.assertIn("native Swift/PDFKit", attempt.detail)
        self.assertEqual([Path(path).name for path in attempt.outputs], ["page-0002.png", "page-0003.png"])
        self.assertIn("import PDFKit", swift_pdf_renderer_source())

    def test_page_contact_sheet_uses_rendered_page_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            page = out_dir / "pages/page-0001.png"
            page.parent.mkdir()
            page.write_text("page")
            report = collect_backend_report(
                which=lambda name: "/opt/homebrew/bin/magick" if name == "magick" else None,
                module_available=lambda _name: False,
            )

            def fake_magick(cmd):
                Path(cmd[-1]).write_text("sheet")
                return True, "ok"

            attempt = try_page_contact_sheet(
                Attempt("page_render", "ok", "rendered", (str(page),)),
                out_dir,
                report,
                run=fake_magick,
            )

        self.assertEqual(attempt.status, "ok")
        self.assertEqual(Path(attempt.outputs[0]).name, "contact_sheet.png")

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
                [
                    Attempt("page_render", "ok", "rendered 2 pages", ("pages/page-0001.png", "pages/page-0002.png")),
                    Attempt("page_contact_sheet", "ok", "created page contact sheet", ("contact_sheet.png",)),
                    Attempt("cover_thumbnail", "ok", "created Quick Look cover thumbnail", ("thumb.png",)),
                ],
            )
            text = notes_path.read_text()

        self.assertIn("PDF Triage Notes: source.pdf", text)
        self.assertIn("`qlmanage`: /usr/bin/qlmanage", text)
        self.assertIn("cover_thumbnail: ok", text)
        self.assertIn("Page images: `pages/`", text)
        self.assertIn("Page contact sheet: `contact_sheet.png`", text)
        self.assertIn("Candidate sweep axes", text)


if __name__ == "__main__":
    unittest.main()
