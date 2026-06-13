from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from blender_workbench.learning_coverage import (  # noqa: E402
    audit_learning_coverage,
    format_learning_coverage_audit,
    format_learning_coverage_report,
    linked_issue_numbers,
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
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root for linked path checks")
    parser.add_argument("--fail-uncovered", action="store_true", help="exit nonzero if any row has no example and no issue")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate", help="validate the coverage schema")
    report = subparsers.add_parser("report", help="print status counts, links, and uncovered prompts")
    report.add_argument("--fail-uncovered", action="store_true", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    audit = subparsers.add_parser("audit", help="check coverage freshness beyond schema validity")
    audit.add_argument("--check-paths", action="store_true", help="check implemented rows for missing linked paths")
    audit.add_argument("--check-issues", action="store_true", help="use gh to check linked GitHub issue states")
    audit.add_argument("--fail-stale", action="store_true", help="exit nonzero when freshness findings are present")
    audit.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    return parser.parse_args(_script_args(argv))


def github_issue_states(issue_numbers: tuple[int, ...]) -> dict[int, str | None]:
    states: dict[int, str | None] = {}
    for issue in issue_numbers:
        completed = subprocess.run(
            ["gh", "issue", "view", str(issue), "--json", "state", "--jq", ".state"],
            cwd=ROOT,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        states[issue] = completed.stdout.strip().lower() if completed.returncode == 0 else None
    return states


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    coverage = load_learning_coverage(args.coverage)
    errors = validate_learning_coverage(coverage)
    if errors:
        raise SystemExit("\n".join(errors))
    uncovered = uncovered_learning_prompts(coverage)
    if args.command == "report":
        print(format_learning_coverage_report(coverage))
    elif args.command == "audit":
        issue_states = github_issue_states(linked_issue_numbers(coverage)) if args.check_issues else None
        findings = audit_learning_coverage(
            coverage,
            root=args.root,
            check_paths=args.check_paths or not args.check_issues,
            issue_states=issue_states,
        )
        if getattr(args, "json", False):
            print(json.dumps(findings, indent=2))
        else:
            print(format_learning_coverage_audit(findings))
        if args.fail_stale and findings:
            raise SystemExit(f"{len(findings)} coverage freshness finding(s)")
    else:
        print(f"{args.coverage} is valid")
    if args.fail_uncovered and uncovered:
        raise SystemExit(f"{len(uncovered)} prompts have no implemented example and no linked issue")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
