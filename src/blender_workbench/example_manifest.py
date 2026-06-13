from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ExamplePreflight:
    name: str
    command: str
    runnable: bool
    missing_prerequisites: tuple[dict[str, str], ...]
    outputs_present: tuple[str, ...]
    outputs_missing: tuple[str, ...]
    docs_asset_present: bool
    docs_asset: str | None = None


def _script_args(argv: list[str] | None = None) -> list[str]:
    values = list(sys.argv[1:] if argv is None else argv)
    if "--" in values:
        return values[values.index("--") + 1 :]
    return values


def default_manifest_path(root: Path | None = None) -> Path:
    root = root or Path.cwd()
    return root / "examples" / "manifest.json"


def load_manifest(path: Path | None = None, *, root: Path | None = None) -> list[dict[str, Any]]:
    manifest_path = path or default_manifest_path(root)
    payload = json.loads(manifest_path.read_text())
    examples = payload.get("examples")
    if not isinstance(examples, list):
        raise ValueError(f"{manifest_path} does not contain an examples list")
    return examples


def select_examples(examples: list[dict[str, Any]], names: list[str] | None = None) -> list[dict[str, Any]]:
    if not names:
        return examples
    wanted = set(names)
    selected = [example for example in examples if example.get("name") in wanted]
    found = {example.get("name") for example in selected}
    missing = sorted(wanted - found)
    if missing:
        raise ValueError(f"Unknown example(s): {', '.join(missing)}")
    return selected


def preflight_example(example: dict[str, Any], *, root: Path | None = None) -> ExamplePreflight:
    root = root or Path.cwd()
    prerequisites = example.get("prerequisites", [])
    missing_prerequisites: list[dict[str, str]] = []
    for prerequisite in prerequisites:
        path = prerequisite.get("path")
        if not path:
            continue
        if not (root / path).exists():
            missing_prerequisites.append(
                {
                    "path": path,
                    "command": prerequisite.get("command", ""),
                    "note": prerequisite.get("note", ""),
                }
            )

    outputs = tuple(example.get("outputs", []))
    outputs_present = tuple(path for path in outputs if (root / path).exists())
    outputs_missing = tuple(path for path in outputs if not (root / path).exists())
    docs_asset = example.get("docs_asset")
    docs_asset_present = bool(docs_asset and (root / docs_asset).exists())
    return ExamplePreflight(
        name=example["name"],
        command=example["command"],
        runnable=not missing_prerequisites,
        missing_prerequisites=tuple(missing_prerequisites),
        outputs_present=outputs_present,
        outputs_missing=outputs_missing,
        docs_asset=docs_asset,
        docs_asset_present=docs_asset_present,
    )


def preflight_examples(
    *,
    manifest_path: Path | None = None,
    root: Path | None = None,
    names: list[str] | None = None,
) -> list[ExamplePreflight]:
    examples = select_examples(load_manifest(manifest_path, root=root), names)
    return [preflight_example(example, root=root) for example in examples]


def format_preflight_report(results: list[ExamplePreflight]) -> str:
    lines = ["Example preflight:", ""]
    for result in results:
        status = "ready" if result.runnable else "blocked"
        output_status = f"{len(result.outputs_present)} outputs present, {len(result.outputs_missing)} missing"
        docs_status = "docs asset present" if result.docs_asset_present else "docs asset missing"
        lines.append(f"- {result.name}: {status}; {output_status}; {docs_status}")
        lines.append(f"  command: {result.command}")
        for missing in result.missing_prerequisites:
            lines.append(f"  missing: {missing['path']}")
            if missing.get("note"):
                lines.append(f"  note: {missing['note']}")
            if missing.get("command"):
                lines.append(f"  upstream: {missing['command']}")
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report example prerequisites, expected outputs, and docs assets.")
    parser.add_argument("--manifest", type=Path, help="manifest path, default examples/manifest.json")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="repository root")
    parser.add_argument("--name", action="append", help="example name to report; repeat for multiple examples")
    parser.add_argument("--json", action="store_true", help="print machine-readable preflight JSON")
    return parser.parse_args(_script_args(argv))


def main(argv: list[str] | None = None) -> list[ExamplePreflight]:
    args = parse_args(argv)
    results = preflight_examples(manifest_path=args.manifest, root=args.root, names=args.name)
    if args.json:
        print(json.dumps([result.__dict__ for result in results], indent=2))
    else:
        print(format_preflight_report(results))
    return results


if __name__ == "__main__":
    main()
