from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


COST_BUCKET_ORDER = {
    "instant": 0,
    "quick": 1,
    "medium": 2,
    "heavy": 3,
    "unknown": 99,
}


@dataclass(frozen=True)
class ExamplePreflight:
    name: str
    command: str
    cost: dict[str, Any]
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


def cost_bucket_rank(bucket: str) -> int:
    try:
        return COST_BUCKET_ORDER[bucket]
    except KeyError as error:
        raise ValueError(f"Unknown cost bucket: {bucket}") from error


def normalized_cost(example: dict[str, Any]) -> dict[str, Any]:
    raw = example.get("cost") or {}
    if not isinstance(raw, dict):
        raise ValueError(f"Example {example.get('name', '<unknown>')} cost must be an object")
    cost = {
        "profile": raw.get("profile", "unknown"),
        "engine": raw.get("engine", "unknown"),
        "runtime": raw.get("runtime", "unknown"),
        "mode": raw.get("mode", "grid_scout"),
        "requires_blender": bool(raw.get("requires_blender", True)),
        "tile_count": raw.get("tile_count"),
        "tile_preset": raw.get("tile_preset"),
        "reuse_outputs": bool(raw.get("reuse_outputs", True)),
    }
    cost_bucket_rank(str(cost["runtime"]))
    return cost


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
        cost=normalized_cost(example),
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
    ready_only: bool = False,
    max_cost: str | None = None,
    sort_by_cost: bool = False,
) -> list[ExamplePreflight]:
    examples = select_examples(load_manifest(manifest_path, root=root), names)
    results = [preflight_example(example, root=root) for example in examples]
    if ready_only:
        results = [result for result in results if result.runnable]
    if max_cost is not None:
        threshold = cost_bucket_rank(max_cost)
        results = [result for result in results if cost_bucket_rank(str(result.cost["runtime"])) <= threshold]
    if sort_by_cost:
        results = sorted(results, key=lambda result: (cost_bucket_rank(str(result.cost["runtime"])), result.name))
    return results


def format_preflight_report(results: list[ExamplePreflight]) -> str:
    lines = ["Example preflight:", ""]
    for result in results:
        status = "ready" if result.runnable else "blocked"
        output_status = f"{len(result.outputs_present)} outputs present, {len(result.outputs_missing)} missing"
        docs_status = "docs asset present" if result.docs_asset_present else "docs asset missing"
        cost = result.cost
        runtime = cost.get("runtime", "unknown")
        profile = cost.get("profile", "unknown")
        engine = cost.get("engine", "unknown")
        mode = cost.get("mode", "unknown")
        blender = "Blender" if cost.get("requires_blender", True) else "no Blender"
        tile_count = cost.get("tile_count")
        tile_text = f"; {tile_count} tiles" if tile_count is not None else ""
        lines.append(f"- {result.name}: {status}; cost {runtime}/{profile}/{engine}/{mode}/{blender}{tile_text}; {output_status}; {docs_status}")
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
    parser.add_argument("--ready-only", action="store_true", help="only include examples whose prerequisites are present")
    parser.add_argument("--max-cost", choices=("instant", "quick", "medium", "heavy"), help="only include examples at or below this runtime bucket")
    parser.add_argument("--sort-by-cost", action="store_true", help="sort examples by runtime bucket before name")
    parser.add_argument("--json", action="store_true", help="print machine-readable preflight JSON")
    return parser.parse_args(_script_args(argv))


def main(argv: list[str] | None = None) -> list[ExamplePreflight]:
    args = parse_args(argv)
    results = preflight_examples(
        manifest_path=args.manifest,
        root=args.root,
        names=args.name,
        ready_only=args.ready_only,
        max_cost=args.max_cost,
        sort_by_cost=args.sort_by_cost,
    )
    if args.json:
        print(json.dumps([asdict(result) for result in results], indent=2))
    else:
        print(format_preflight_report(results))
    return results


if __name__ == "__main__":
    main()
