from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any, Callable, Iterable


INDEX_SCHEMA = 1
DEFAULT_INDEX_PATH = Path("pdf_lesson_index.json")
DEFAULT_PDF_DIR = Path("../reference_materials/artistic_blender_pdfs")
DEFAULT_REFERENCE_MANIFEST = Path("reference_manifest.json")
LESSON_STATUSES = ("unskimmed", "candidate", "triaged", "issue_open", "implemented", "skipped")
QUEUE_STATUSES = ("candidate", "unskimmed")

PRIORITY_HINTS = (
    ("cg_lighting", 95),
    ("lighting_rendering", 90),
    ("compositing", 82),
    ("texturing_environment_lighting", 78),
    ("blender_basics", 45),
    ("general_inspiration", 35),
)

TAG_HINTS = {
    "lighting": ("lighting",),
    "rendering": ("rendering",),
    "texturing": ("texture",),
    "environment": ("environment",),
    "compositing": ("compositing", "postprocess"),
    "basics": ("fundamentals", "obsolete_ui"),
    "inspiration": ("inspiration",),
}


def _script_args(argv: list[str] | None = None) -> list[str]:
    values = list(sys.argv[1:] if argv is None else argv)
    if "--" in values:
        return values[values.index("--") + 1 :]
    return values


def _run(cmd: list[str]) -> tuple[bool, str]:
    try:
        completed = subprocess.run(cmd, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True, completed.stdout.strip() or completed.stderr.strip()
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        return False, detail.strip()


def relpath(path: Path, root: Path) -> str:
    return Path(os.path.relpath(path.resolve(), root.resolve())).as_posix()


def dedupe(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def source_title(stem: str) -> str:
    words = stem.replace("_", " ").replace("-", " ").split()
    return " ".join(word.upper() if word.lower() in {"cg", "sss", "pdf"} else word.capitalize() for word in words)


def default_priority(source_id: str, title: str) -> int:
    haystack = f"{source_id} {title}".lower()
    for needle, priority in PRIORITY_HINTS:
        if needle in haystack:
            return priority
    return 50


def infer_tags(source_id: str, title: str) -> list[str]:
    haystack = f"{source_id} {title}".lower()
    tags: list[str] = []
    for needle, values in TAG_HINTS.items():
        if needle in haystack:
            tags.extend(values)
    return dedupe(tags)


def read_page_count_mdls(pdf: Path, *, runner: Callable[[list[str]], tuple[bool, str]] = _run) -> int | None:
    ok, output = runner(["mdls", "-raw", "-name", "kMDItemNumberOfPages", str(pdf)])
    if not ok:
        return None
    try:
        value = int(output.splitlines()[0].strip())
    except (IndexError, ValueError):
        return None
    return value if value > 0 else None


def load_index(path: Path = DEFAULT_INDEX_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text())
    if payload.get("schema") != INDEX_SCHEMA:
        raise ValueError(f"{path} schema must be {INDEX_SCHEMA}")
    if not isinstance(payload.get("sources"), list):
        raise ValueError(f"{path} does not contain a sources list")
    return payload


def write_index(index: dict[str, Any], path: Path = DEFAULT_INDEX_PATH) -> Path:
    path.write_text(json.dumps(index, indent=2) + "\n")
    return path


def reference_pdf_resources(path: Path, *, root: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text())
    resources = {}
    for resource in payload.get("resources", []):
        if resource.get("type") != "pdf":
            continue
        pdf_path = Path(resource["path"])
        resolved = pdf_path if pdf_path.is_absolute() else (root / pdf_path).resolve()
        resources[resolved.name] = resource
    return resources


def build_lesson_index(
    pdf_dir: Path,
    *,
    root: Path | None = None,
    existing: dict[str, Any] | None = None,
    reference_manifest: Path | None = DEFAULT_REFERENCE_MANIFEST,
    page_count_reader: Callable[[Path], int | None] = read_page_count_mdls,
) -> dict[str, Any]:
    root = root or Path.cwd()
    pdf_dir = pdf_dir if pdf_dir.is_absolute() else root / pdf_dir
    if reference_manifest is not None:
        reference_manifest = reference_manifest if reference_manifest.is_absolute() else root / reference_manifest
    existing_sources = {source["source_id"]: source for source in (existing or {}).get("sources", [])}
    reference_resources = reference_pdf_resources(reference_manifest or Path(""), root=root) if reference_manifest else {}
    sources = []
    for pdf in sorted(Path(pdf_dir).glob("*.pdf")):
        resource = reference_resources.get(pdf.name, {})
        source_id = resource.get("id") or pdf.stem
        previous = existing_sources.get(source_id, {})
        page_count = page_count_reader(pdf) or previous.get("page_count")
        title = previous.get("title") or source_title(pdf.stem)
        tags = dedupe([*previous.get("tags", []), *infer_tags(source_id, title)])
        priority = previous.get("priority", default_priority(source_id, title))
        sources.append(
            {
                "source_id": source_id,
                "resource_id": resource.get("id"),
                "title": title,
                "path": relpath(pdf, root),
                "page_count": page_count,
                "status": previous.get("status", "unskimmed"),
                "priority": priority,
                "tags": tags,
                "source_url": resource.get("source_url"),
                "sha256": resource.get("sha256"),
                "ranges": previous.get("ranges", []),
            }
        )
    return {
        "schema": INDEX_SCHEMA,
        "updated": date.today().isoformat(),
        "status_values": list(LESSON_STATUSES),
        "queue_status_values": list(QUEUE_STATUSES),
        "sources": sources,
    }


def parse_pages(value: str) -> tuple[int, int]:
    first_text, sep, last_text = value.partition("-")
    first = int(first_text)
    last = int(last_text) if sep else first
    if first < 1 or last < first:
        raise ValueError(f"Invalid page range: {value}")
    return first, last


def pages_text(first: int, last: int) -> str:
    return str(first) if first == last else f"{first}-{last}"


def triage_command(source: dict[str, Any], pages: str) -> str:
    first, last = parse_pages(pages)
    return f"python3 tools/pdf_triage.py {source['path']} --first-page {first} --last-page {last}"


def find_source(index: dict[str, Any], source_id: str) -> dict[str, Any]:
    matches = [source for source in index["sources"] if source["source_id"] == source_id]
    if not matches:
        matches = [source for source in index["sources"] if source["source_id"].startswith(source_id)]
    if len(matches) == 1:
        return matches[0]
    if matches:
        options = ", ".join(source["source_id"] for source in matches)
        raise ValueError(f"Source {source_id!r} is ambiguous: {options}")
    raise ValueError(f"Unknown source: {source_id}")


def mark_range(
    index: dict[str, Any],
    *,
    source_id: str,
    pages: str,
    status: str,
    title: str | None = None,
    priority: int | None = None,
    tags: Iterable[str] = (),
    issue: int | None = None,
    triage_output: str | None = None,
    coverage_entry: str | None = None,
    example: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    if status not in LESSON_STATUSES:
        raise ValueError(f"Unknown status: {status}")
    first, last = parse_pages(pages)
    normalized_pages = pages_text(first, last)
    source = find_source(index, source_id)
    ranges = source.setdefault("ranges", [])
    matches = [entry for entry in ranges if entry.get("pages") == normalized_pages]
    entry = matches[0] if matches else {"pages": normalized_pages}
    if not matches:
        ranges.append(entry)
    if title:
        entry["title"] = title
    entry["status"] = status
    if priority is not None:
        entry["priority"] = priority
    entry["tags"] = dedupe([*entry.get("tags", []), *tags])
    if issue is not None:
        entry["issue"] = issue
    if triage_output:
        entry["triage_output"] = triage_output
    if coverage_entry:
        entry["coverage_entry"] = coverage_entry
    if example:
        entry["example"] = example
    if note:
        entry["note"] = note
    if source.get("status") in {"unskimmed", "candidate"}:
        source["status"] = status
    index["updated"] = date.today().isoformat()
    return entry


def parse_toc_entry(value: str) -> dict[str, Any]:
    pages, sep, title_tags = value.partition("=")
    if not sep:
        raise ValueError(f"TOC entry must use PAGES=TITLE[:tag,tag]: {value}")
    title, tag_sep, tag_text = title_tags.partition(":")
    title = title.strip()
    if not title:
        raise ValueError(f"TOC entry is missing a title: {value}")
    first, last = parse_pages(pages.strip())
    tags = [tag.strip() for tag in tag_text.split(",")] if tag_sep else []
    return {"pages": pages_text(first, last), "title": title, "tags": dedupe(tags)}


def import_toc_ranges(
    index: dict[str, Any],
    *,
    source_id: str,
    entries: Iterable[str],
    status: str = "candidate",
    tags: Iterable[str] = (),
    priority: int | None = None,
    triage_output: str | None = None,
    note: str | None = "TOC",
) -> list[dict[str, Any]]:
    imported = []
    for raw_entry in entries:
        parsed = parse_toc_entry(raw_entry)
        entry_note = f"{note}: {parsed['title']}" if note else None
        imported.append(
            mark_range(
                index,
                source_id=source_id,
                pages=parsed["pages"],
                status=status,
                title=parsed["title"],
                priority=priority,
                tags=[*tags, *parsed["tags"]],
                triage_output=triage_output,
                note=entry_note,
            )
        )
    return imported


def next_items(
    index: dict[str, Any],
    *,
    limit: int = 5,
    statuses: Iterable[str] = QUEUE_STATUSES,
) -> list[dict[str, Any]]:
    wanted = tuple(statuses)
    status_rank = {status: rank for rank, status in enumerate(wanted)}
    items = []
    for source in index["sources"]:
        pending_ranges = [entry for entry in source.get("ranges", []) if entry.get("status") in wanted]
        for entry in pending_ranges:
            items.append(
                {
                    "source_id": source["source_id"],
                    "title": source["title"],
                    "range_title": entry.get("title"),
                    "pages": entry["pages"],
                    "status": entry["status"],
                    "priority": entry.get("priority", source.get("priority", 50)),
                    "tags": dedupe([*source.get("tags", []), *entry.get("tags", [])]),
                    "triage_command": triage_command(source, entry["pages"]),
                }
            )
        if not pending_ranges and source.get("status") in wanted:
            page_count = source.get("page_count") or 8
            pages = pages_text(1, min(8, page_count))
            items.append(
                {
                    "source_id": source["source_id"],
                    "title": source["title"],
                    "pages": pages,
                    "status": source.get("status", "unskimmed"),
                    "priority": source.get("priority", 50),
                    "tags": source.get("tags", []),
                    "triage_command": triage_command(source, pages),
                }
            )
    items.sort(key=lambda item: (status_rank.get(item["status"], 99), -int(item["priority"]), item["source_id"]))
    return items[:limit]


def format_index_report(index: dict[str, Any]) -> str:
    lines = ["PDF lesson index:", ""]
    for source in index["sources"]:
        ranges = source.get("ranges", [])
        lines.append(
            f"- {source['source_id']}: {source['status']}; {source.get('page_count') or '?'} pages; "
            f"priority {source.get('priority', 50)}; {len(ranges)} range(s)"
        )
    return "\n".join(lines)


def format_queue_report(items: list[dict[str, Any]]) -> str:
    lines = ["Next PDF skim queue:", ""]
    for item in items:
        tag_text = f"; tags {', '.join(item['tags'])}" if item.get("tags") else ""
        range_title = f"; {item['range_title']}" if item.get("range_title") else ""
        lines.append(
            f"- {item['source_id']} pages {item['pages']}: {item['status']}; "
            f"priority {item['priority']}{range_title}{tag_text}"
        )
        lines.append(f"  triage: {item['triage_command']}")
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build and maintain a PDF lesson index and skim queue.")
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX_PATH, help="lesson index JSON path")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="repository root for relative paths")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    subparsers = parser.add_subparsers(dest="command")

    build_parser = subparsers.add_parser("build", help="scan a PDF shelf and create/update the index")
    build_parser.add_argument("pdf_dir", nargs="?", type=Path, default=DEFAULT_PDF_DIR)
    build_parser.add_argument("--reference-manifest", type=Path, default=DEFAULT_REFERENCE_MANIFEST)
    build_parser.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help=argparse.SUPPRESS)

    next_parser = subparsers.add_parser("next", help="show recommended ranges to skim next")
    next_parser.add_argument("--limit", type=int, default=5)
    next_parser.add_argument("--status", action="append", choices=LESSON_STATUSES, help="status to include; repeatable")
    next_parser.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help=argparse.SUPPRESS)

    mark_parser = subparsers.add_parser("mark", help="add or update a page-range status")
    mark_parser.add_argument("--source", required=True, help="source id or unique prefix")
    mark_parser.add_argument("--pages", required=True, help="page or page range, e.g. 12-15")
    mark_parser.add_argument("--status", required=True, choices=LESSON_STATUSES)
    mark_parser.add_argument("--tag", action="append", default=[])
    mark_parser.add_argument("--issue", type=int)
    mark_parser.add_argument("--triage-output")
    mark_parser.add_argument("--coverage-entry")
    mark_parser.add_argument("--example")
    mark_parser.add_argument("--note")
    mark_parser.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help=argparse.SUPPRESS)

    toc_parser = subparsers.add_parser("import-toc", help="promote contents-page entries into candidate ranges")
    toc_parser.add_argument("source", help="source id or unique prefix")
    toc_parser.add_argument("--entry", action="append", required=True, help="PAGES=TITLE[:tag,tag], e.g. 10-11=Mesh Lights:lighting")
    toc_parser.add_argument("--status", default="candidate", choices=LESSON_STATUSES)
    toc_parser.add_argument("--tag", action="append", default=[])
    toc_parser.add_argument("--priority", type=int)
    toc_parser.add_argument("--triage-output")
    toc_parser.add_argument("--note", default="TOC")
    toc_parser.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    return parser.parse_args(_script_args(argv))


def main(argv: list[str] | None = None) -> dict[str, Any] | list[dict[str, Any]]:
    args = parse_args(argv)
    command = args.command or "next"
    if command == "build":
        existing = load_index(args.index) if args.index.exists() else None
        index = build_lesson_index(
            args.pdf_dir,
            root=args.root,
            existing=existing,
            reference_manifest=args.reference_manifest,
        )
        write_index(index, args.index)
        if args.json:
            print(json.dumps(index, indent=2))
        else:
            print(f"Wrote {args.index}")
            print(format_index_report(index))
        return index

    index = load_index(args.index)
    if command == "mark":
        entry = mark_range(
            index,
            source_id=args.source,
            pages=args.pages,
            status=args.status,
            tags=args.tag,
            issue=args.issue,
            triage_output=args.triage_output,
            coverage_entry=args.coverage_entry,
            example=args.example,
            note=args.note,
        )
        write_index(index, args.index)
        if args.json:
            print(json.dumps(entry, indent=2))
        else:
            print(f"Marked {args.source} pages {entry['pages']} as {entry['status']}")
        return entry

    if command == "import-toc":
        entries = import_toc_ranges(
            index,
            source_id=args.source,
            entries=args.entry,
            status=args.status,
            tags=args.tag,
            priority=args.priority,
            triage_output=args.triage_output,
            note=args.note,
        )
        write_index(index, args.index)
        if args.json:
            print(json.dumps(entries, indent=2))
        else:
            print(f"Imported {len(entries)} TOC range(s) for {args.source}")
        return entries

    items = next_items(index, limit=args.limit, statuses=args.status or QUEUE_STATUSES)
    if args.json:
        print(json.dumps(items, indent=2))
    else:
        print(format_queue_report(items))
    return items


if __name__ == "__main__":
    main()
