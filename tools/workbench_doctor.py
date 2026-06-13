from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from blender_workbench.capabilities import collect_capability_report, format_capability_report


def _script_args(argv: list[str] | None = None) -> list[str]:
    values = list(sys.argv[1:] if argv is None else argv)
    if "--" in values:
        return values[values.index("--") + 1 :]
    return values


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report local Blender Workbench tool and feature capabilities.")
    parser.add_argument("--json", action="store_true", help="print machine-readable capability JSON")
    parser.add_argument("--no-versions", action="store_true", help="skip cheap command version probes")
    parser.add_argument("--require-ready", action="store_true", help="exit nonzero when any capability group is blocked")
    return parser.parse_args(_script_args(argv))


def main(argv: list[str] | None = None) -> dict:
    args = parse_args(argv)
    report = collect_capability_report(check_versions=not args.no_versions)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(format_capability_report(report))
    if args.require_ready and report["status"] != "ready":
        raise SystemExit(1)
    return report


if __name__ == "__main__":
    main()
