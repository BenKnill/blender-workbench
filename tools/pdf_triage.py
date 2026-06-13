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
from typing import Callable


COMMAND_BACKENDS = ("pdftotext", "pdfinfo", "pdftoppm", "gs", "magick", "qlmanage", "sips", "mdls")
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
        return Attempt("thumbnail", "skipped", "qlmanage is not available")
    ok, detail = _run(["qlmanage", "-t", "-s", "900", "-o", str(out_dir), str(pdf)])
    if not ok:
        return Attempt("thumbnail", "failed", detail)
    outputs = tuple(str(path) for path in sorted(out_dir.glob(f"{pdf.name}*.png")))
    return Attempt("thumbnail", "ok", "created Quick Look thumbnail", outputs)


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
        try_quicklook_thumbnail(pdf, out_dir, report),
    ]
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
