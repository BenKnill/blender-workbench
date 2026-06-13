from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from blender_workbench.learning_coverage import (  # noqa: E402
    format_learning_coverage_report,
    load_learning_coverage,
    uncovered_learning_prompts,
    validate_learning_coverage,
)


def _script_args(argv: list[str] | None = None) -> list[str]:
    values = list(sys.argv[1:] if argv is None else argv)
    if "--" in values:
        return values[values.index("--") + 1 :]
    return values


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate or report learning-resource coverage.")
    parser.add_argument("--coverage", type=Path, default=ROOT / "docs" / "learning-coverage.json")
    parser.add_argument("--fail-uncovered", action="store_true", help="exit nonzero if any row has no example and no issue")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate", help="validate the coverage schema")
    report = subparsers.add_parser("report", help="print status counts, links, and uncovered prompts")
    report.add_argument("--fail-uncovered", action="store_true", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    return parser.parse_args(_script_args(argv))


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    coverage = load_learning_coverage(args.coverage)
    errors = validate_learning_coverage(coverage)
    if errors:
        raise SystemExit("\n".join(errors))
    uncovered = uncovered_learning_prompts(coverage)
    if args.command == "report":
        print(format_learning_coverage_report(coverage))
    else:
        print(f"{args.coverage} is valid")
    if args.fail_uncovered and uncovered:
        raise SystemExit(f"{len(uncovered)} prompts have no implemented example and no linked issue")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
