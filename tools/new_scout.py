from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from blender_workbench.new_scout import (  # noqa: E402
    build_scout_plan,
    format_scout_plan,
    plan_to_jsonable,
    write_scout_scaffold,
)


def _script_args(argv: list[str] | None = None) -> list[str]:
    values = list(sys.argv[1:] if argv is None else argv)
    if "--" in values:
        return values[values.index("--") + 1 :]
    return values


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan or create the files for a new workbench scout.")
    parser.add_argument("--name", required=True, help="short scout name, for example caustic_water")
    parser.add_argument("--kind", default="recipe", help="scaffold category label")
    parser.add_argument("--docs-title", help="human title for docs and selected render output")
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root")
    parser.add_argument("--no-pick", action="store_true", help="mark selected-render promotion as not applicable")
    parser.add_argument("--write", action="store_true", help="write template files instead of dry-run only")
    parser.add_argument("--force", action="store_true", help="allow --write to overwrite template files")
    parser.add_argument("--json", action="store_true", help="print the plan as JSON")
    parser.add_argument("--dry-run", action="store_true", help="print the plan without writing files")
    return parser.parse_args(_script_args(argv))


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    plan = build_scout_plan(
        name=args.name,
        docs_title=args.docs_title,
        kind=args.kind,
        promotion_applicable=not args.no_pick,
    )
    if args.write:
        written = write_scout_scaffold(plan, root=args.root, force=args.force)
        print(f"Wrote {len(written)} scaffold files:")
        for path in written:
            print(f"- {path}")
    if args.json:
        print(json.dumps(plan_to_jsonable(plan), indent=2))
    else:
        print(format_scout_plan(plan))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
