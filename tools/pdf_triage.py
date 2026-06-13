from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from textwrap import dedent
from typing import Callable


COMMAND_BACKENDS = ("pdftotext", "pdfinfo", "pdftoppm", "gs", "magick", "qlmanage", "sips", "mdls", "swift")
PYTHON_BACKENDS = ("pypdf", "PyPDF2", "pdfplumber", "fitz")


@dataclass(frozen=True)
class Attempt:
    name: str
    status: str
    detail: str
    outputs: tuple[str, ...] = ()


def _script_args(argv: list[str] | None = None) -> list[str]:
    values = list(sys.argv[1:] if argv is None else argv)
    if "--" in values:
        return values[values.index("--") + 1 :]
    return values


def default_out_dir(pdf: Path, root: Path | None = None) -> Path:
    root = root or Path.cwd()
    return root / "runs" / "pdf_triage" / pdf.stem


def collect_backend_report(
    *,
    which: Callable[[str], str | None] = shutil.which,
    module_available: Callable[[str], bool] | None = None,
) -> dict[str, dict[str, str | bool | None]]:
    module_available = module_available or (lambda name: importlib.util.find_spec(name) is not None)
    commands = {name: {"available": bool(path := which(name)), "path": path} for name in COMMAND_BACKENDS}
    modules = {name: {"available": module_available(name)} for name in PYTHON_BACKENDS}
    return {"commands": commands, "python_modules": modules}


def _run(cmd: list[str]) -> tuple[bool, str]:
    try:
        completed = subprocess.run(cmd, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        detail = completed.stdout.strip() or completed.stderr.strip() or "ok"
        return True, detail
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        stderr = getattr(exc, "stderr", "") or str(exc)
        return False, stderr.strip()


def try_pdfinfo(pdf: Path, out_dir: Path, report: dict[str, dict[str, str | bool | None]]) -> Attempt:
    backend = report["commands"].get("pdfinfo", {})
    if not backend.get("available"):
        return Attempt("pdfinfo", "skipped", "pdfinfo is not available")
    out_path = out_dir / "pdfinfo.txt"
    ok, detail = _run(["pdfinfo", str(pdf)])
    if ok:
        out_path.write_text(f"{detail}\n")
        return Attempt("pdfinfo", "ok", "wrote pdfinfo output", (str(out_path),))
    return Attempt("pdfinfo", "failed", detail)


def try_text_extract(pdf: Path, out_dir: Path, report: dict[str, dict[str, str | bool | None]], first_page: int, last_page: int) -> Attempt:
    backend = report["commands"].get("pdftotext", {})
    if not backend.get("available"):
        return Attempt("text", "skipped", "pdftotext is not available")
    out_path = out_dir / "text.txt"
    ok, detail = _run(["pdftotext", "-layout", "-f", str(first_page), "-l", str(last_page), str(pdf), str(out_path)])
    if ok:
        return Attempt("text", "ok", f"extracted pages {first_page}-{last_page}", (str(out_path),))
    return Attempt("text", "failed", detail)


def try_quicklook_thumbnail(pdf: Path, out_dir: Path, report: dict[str, dict[str, str | bool | None]]) -> Attempt:
    backend = report["commands"].get("qlmanage", {})
    if not backend.get("available"):
        return Attempt("cover_thumbnail", "skipped", "qlmanage is not available")
    ok, detail = _run(["qlmanage", "-t", "-s", "900", "-o", str(out_dir), str(pdf)])
    if not ok:
        return Attempt("cover_thumbnail", "failed", detail)
    outputs = tuple(str(path) for path in sorted(out_dir.glob(f"{pdf.name}*.png")))
    return Attempt("cover_thumbnail", "ok", "created Quick Look cover thumbnail", outputs)


def swift_pdf_renderer_source() -> str:
    return dedent(
        r"""
        import AppKit
        import Foundation
        import PDFKit

        let args = CommandLine.arguments
        guard args.count == 6 else {
            fputs("usage: render_pdf_pages.swift PDF OUT_DIR FIRST_PAGE LAST_PAGE DPI\n", stderr)
            exit(64)
        }

        let pdfURL = URL(fileURLWithPath: args[1])
        let outURL = URL(fileURLWithPath: args[2], isDirectory: true)
        let firstPage = max(1, Int(args[3]) ?? 1)
        let requestedLastPage = max(firstPage, Int(args[4]) ?? firstPage)
        let dpi = max(36.0, Double(args[5]) ?? 144.0)

        guard let document = PDFDocument(url: pdfURL) else {
            fputs("could not open PDF: \(pdfURL.path)\n", stderr)
            exit(65)
        }
        let pageCount = document.pageCount
        guard pageCount > 0 else {
            fputs("PDF has no pages: \(pdfURL.path)\n", stderr)
            exit(66)
        }
        guard firstPage <= pageCount else {
            fputs("first page \(firstPage) is past page count \(pageCount)\n", stderr)
            exit(67)
        }

        try FileManager.default.createDirectory(at: outURL, withIntermediateDirectories: true)
        let lastPage = min(requestedLastPage, pageCount)
        let scale = dpi / 72.0

        for pageNumber in firstPage...lastPage {
            guard let page = document.page(at: pageNumber - 1) else { continue }
            let bounds = page.bounds(for: .mediaBox)
            let width = max(1, Int(bounds.width * scale))
            let height = max(1, Int(bounds.height * scale))
            let image = NSImage(size: NSSize(width: width, height: height))

            image.lockFocus()
            NSColor.white.setFill()
            NSRect(x: 0, y: 0, width: width, height: height).fill()
            if let context = NSGraphicsContext.current?.cgContext {
                context.saveGState()
                context.scaleBy(x: scale, y: scale)
                page.draw(with: .mediaBox, to: context)
                context.restoreGState()
            }
            image.unlockFocus()

            guard
                let tiff = image.tiffRepresentation,
                let rep = NSBitmapImageRep(data: tiff),
                let data = rep.representation(using: .png, properties: [:])
            else {
                fputs("could not encode page \(pageNumber)\n", stderr)
                exit(68)
            }

            let output = outURL.appendingPathComponent(String(format: "page-%04d.png", pageNumber))
            try data.write(to: output)
            print(output.path)
        }
        """
    ).strip()


def try_native_macos_page_render(
    pdf: Path,
    out_dir: Path,
    report: dict[str, dict[str, str | bool | None]],
    first_page: int,
    last_page: int,
    *,
    dpi: int = 144,
    run: Callable[[list[str]], tuple[bool, str]] = _run,
    platform: str | None = None,
) -> Attempt:
    backend = report["commands"].get("swift", {})
    current_platform = platform or sys.platform
    if current_platform != "darwin":
        return Attempt("page_render", "skipped", "native Swift/PDFKit page rendering is only available on macOS")
    if not backend.get("available"):
        return Attempt("page_render", "skipped", "swift is not available")
    pages_dir = out_dir / "pages"
    script_path = out_dir / "_render_pdf_pages.swift"
    script_path.write_text(swift_pdf_renderer_source())
    ok, detail = run(["swift", str(script_path), str(pdf), str(pages_dir), str(first_page), str(last_page), str(dpi)])
    outputs = tuple(str(path) for path in sorted(pages_dir.glob("page-*.png")))
    if ok and outputs:
        return Attempt("page_render", "ok", f"rendered {len(outputs)} page image(s) with native Swift/PDFKit", outputs)
    if ok:
        return Attempt("page_render", "failed", "Swift/PDFKit completed but produced no page images")
    return Attempt("page_render", "failed", detail)


def try_page_contact_sheet(
    page_render: Attempt,
    out_dir: Path,
    report: dict[str, dict[str, str | bool | None]],
    *,
    run: Callable[[list[str]], tuple[bool, str]] = _run,
) -> Attempt:
    if page_render.status != "ok" or not page_render.outputs:
        return Attempt("page_contact_sheet", "skipped", "page images are not available")
    backend = report["commands"].get("magick", {})
    if not backend.get("available"):
        return Attempt("page_contact_sheet", "skipped", "magick is not available")
    contact_sheet = out_dir / "contact_sheet.png"
    ok, detail = run(
        [
            "magick",
            *page_render.outputs,
            "-thumbnail",
            "240x320",
            "-background",
            "white",
            "-gravity",
            "center",
            "-extent",
            "240x320",
            "+append",
            str(contact_sheet),
        ]
    )
    if ok and contact_sheet.exists():
        return Attempt("page_contact_sheet", "ok", "created page contact sheet from rendered page images", (str(contact_sheet),))
    if contact_sheet.exists():
        return Attempt("page_contact_sheet", "ok", f"created page contact sheet with warning: {detail}", (str(contact_sheet),))
    if ok:
        return Attempt("page_contact_sheet", "failed", "magick completed but did not write contact_sheet.png")
    return Attempt("page_contact_sheet", "failed", detail)


def write_notes_template(pdf: Path, out_dir: Path, report: dict[str, dict[str, str | bool | None]], attempts: list[Attempt]) -> Path:
    notes_path = out_dir / "notes.md"
    lines = [
        f"# PDF Triage Notes: {pdf.name}",
        "",
        f"Source: `{pdf}`",
        f"Created: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Backend Report",
        "",
    ]
    for name, status in report["commands"].items():
        value = status.get("path") or "missing"
        lines.append(f"- `{name}`: {value}")
    for name, status in report["python_modules"].items():
        value = "available" if status.get("available") else "missing"
        lines.append(f"- Python `{name}`: {value}")
    lines.extend(["", "## Attempted Outputs", ""])
    for attempt in attempts:
        outputs = ", ".join(f"`{Path(path).name}`" for path in attempt.outputs) if attempt.outputs else "none"
        lines.append(f"- {attempt.name}: {attempt.status}; {attempt.detail}; outputs: {outputs}")
    page_render = next((attempt for attempt in attempts if attempt.name == "page_render" and attempt.status == "ok"), None)
    contact_sheet = next((attempt for attempt in attempts if attempt.name == "page_contact_sheet" and attempt.status == "ok"), None)
    if page_render or contact_sheet:
        lines.extend(["", "## Visual Evidence", ""])
        if page_render:
            lines.append("- Page images: `pages/`")
        if contact_sheet and contact_sheet.outputs:
            lines.append(f"- Page contact sheet: `{Path(contact_sheet.outputs[0]).name}`")
    lines.extend(
        [
            "",
            "## Page Observations",
            "",
            "- Page/range:",
            "- Visual or workflow lesson:",
            "- Candidate sweep axes:",
            "- Existing recipe connection:",
            "- Follow-up issue or PR:",
            "",
            "## Notes For docs/learning-notes.md",
            "",
            "- Source file:",
            "- Lesson:",
            "- Implemented recipe or next workflow gap:",
            "",
        ]
    )
    notes_path.write_text("\n".join(lines))
    return notes_path


def triage_pdf(pdf: Path, out_dir: Path | None = None, *, first_page: int = 1, last_page: int = 3) -> dict[str, object]:
    pdf = pdf.resolve()
    if not pdf.exists():
        raise FileNotFoundError(pdf)
    out_dir = (out_dir or default_out_dir(pdf)).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    report = collect_backend_report()
    attempts = [
        try_pdfinfo(pdf, out_dir, report),
        try_text_extract(pdf, out_dir, report, first_page, last_page),
    ]
    page_render = try_native_macos_page_render(pdf, out_dir, report, first_page, last_page)
    attempts.extend(
        [
            page_render,
            try_page_contact_sheet(page_render, out_dir, report),
        ]
    )
    attempts.extend(
        [
            try_quicklook_thumbnail(pdf, out_dir, report),
        ]
    )
    notes_path = write_notes_template(pdf, out_dir, report, attempts)
    payload = {
        "source_pdf": str(pdf),
        "out_dir": str(out_dir),
        "backend_report": report,
        "attempts": [attempt.__dict__ for attempt in attempts],
        "notes": str(notes_path),
    }
    (out_dir / "triage.json").write_text(json.dumps(payload, indent=2))
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture PDF extraction/rendering backends and create a learning-notes triage stub.")
    parser.add_argument("pdf", type=Path, help="PDF to triage")
    parser.add_argument("--out", type=Path, help="output directory, default runs/pdf_triage/<pdf-stem>")
    parser.add_argument("--first-page", type=int, default=1, help="first page for text extraction when pdftotext is available")
    parser.add_argument("--last-page", type=int, default=3, help="last page for text extraction when pdftotext is available")
    return parser.parse_args(_script_args(argv))


def main(argv: list[str] | None = None) -> dict[str, object]:
    args = parse_args(argv)
    result = triage_pdf(args.pdf, args.out, first_page=args.first_page, last_page=args.last_page)
    print(f"Wrote PDF triage to {result['out_dir']}")
    return result


if __name__ == "__main__":
    main()
