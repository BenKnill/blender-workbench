from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from blender_workbench.artifact_index import build_artifact_index, format_artifact_report, validate_artifact_index


def _script_args(argv: list[str] | None = None) -> list[str]:
    values = list(sys.argv[1:] if argv is None else argv)
    if "--" in values:
        return values[values.index("--") + 1 :]
    return values


def _default_paths() -> list[Path]:
    return [
        ROOT / "examples" / "output",
        ROOT / "runs",
        ROOT.parent / "spacex_vacuum_plume_sweep",
        ROOT.parent / "blender_art_exercises",
        ROOT.parent / "fast_distinct_lighting_studies_v2",
    ]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build or inspect a versioned artifact index.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="scan paths and write an index JSON")
    build.add_argument("paths", nargs="*", type=Path, help="paths to scan; defaults to known output and legacy folders")
    build.add_argument("--root", type=Path, default=ROOT, help="repository root for relative paths")
    build.add_argument("--out", type=Path, default=ROOT / "artifacts" / "index.json", help="index output path")

    report = subparsers.add_parser("report", help="print type/status/preview/source report")
    report.add_argument("paths", nargs="*", type=Path, help="paths to scan when --index is omitted")
    report.add_argument("--root", type=Path, default=ROOT, help="repository root for relative paths")
    report.add_argument("--index", type=Path, help="read an existing index JSON instead of scanning")

    validate = subparsers.add_parser("validate", help="validate an index JSON or scanned artifact paths")
    validate.add_argument("paths", nargs="*", type=Path, help="paths to scan when --scan is used")
    validate.add_argument("--index", type=Path, default=ROOT / "artifacts" / "index.json", help="index JSON path")
    validate.add_argument("--root", type=Path, default=ROOT, help="repository root for relative paths when scanning")
    validate.add_argument("--scan", action="store_true", help="scan paths and validate the in-memory index without writing it")

    return parser.parse_args(_script_args(argv))


def _load_index(path: Path) -> dict:
    return json.loads(path.read_text())


def _scan(paths: list[Path], *, root: Path) -> dict:
    return build_artifact_index(paths or _default_paths(), root=root)


def main(argv: list[str] | None = None) -> dict:
    args = parse_args(argv)
    if args.command == "build":
        index = _scan(args.paths, root=args.root)
        errors = validate_artifact_index(index)
        if errors:
            raise SystemExit("\n".join(errors))
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(index, indent=2) + "\n")
        print(f"Wrote {args.out} ({len(index['artifacts'])} artifacts)")
        return index
    if args.command == "report":
        index = _load_index(args.index) if args.index else _scan(args.paths, root=args.root)
        print(format_artifact_report(index))
        return index
    if args.command == "validate":
        if args.scan:
            index = _scan(args.paths, root=args.root)
            source = "scanned artifact index"
        else:
            if not args.index.exists():
                raise SystemExit(
                    f"No {args.index} found; run `python3 tools/artifact_index.py build --out {args.index}` "
                    "or `python3 tools/artifact_index.py validate --scan`."
                )
            index = _load_index(args.index)
            source = str(args.index)
        errors = validate_artifact_index(index)
        if errors:
            raise SystemExit("\n".join(errors))
        print(f"{source} is valid")
        return index
    raise SystemExit(f"Unknown command {args.command}")


if __name__ == "__main__":
    main()
