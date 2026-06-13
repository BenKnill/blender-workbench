from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from blender_workbench.review_log import REVIEW_ACTIONS, write_review_log


def _script_args(argv: list[str] | None = None) -> list[str]:
    values = list(sys.argv[1:] if argv is None else argv)
    if "--" in values:
        return values[values.index("--") + 1 :]
    return values


def _key_value(items: list[str] | None, *, default_value: str = "") -> dict[str, str]:
    values: dict[str, str] = {}
    for item in items or []:
        key, sep, value = item.partition("=")
        values[key] = value if sep else default_value
    return values


def _tags(items: list[str] | None) -> dict[str, list[str]]:
    values: dict[str, list[str]] = {}
    for item in items or []:
        key, sep, value = item.partition("=")
        if not sep:
            raise ValueError("--tag must be written as NAME=tag")
        values.setdefault(key, []).append(value)
    return values


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write structured review.json notes for an existing sweep.")
    parser.add_argument("sweep_dir", type=Path, help="sweep output directory containing metadata.json")
    parser.add_argument("--winner", help="variant name selected as the winner")
    parser.add_argument("--promising", action="append", default=[], help="variant name worth keeping as an alternate")
    parser.add_argument("--reject", action="append", default=[], help="variant rejection as NAME=reason")
    parser.add_argument("--failure-anchor", action="append", default=[], help="variant name that is useful as a failure anchor")
    parser.add_argument("--tag", action="append", default=[], help="qualitative tag as NAME=tag")
    parser.add_argument("--next-action", choices=REVIEW_ACTIONS, help="recommended next workflow action")
    parser.add_argument("--next", dest="next_note", help="freeform next-run note or stride/axis hint")
    parser.add_argument("--reviewer", default=getpass.getuser() or "codex", help="reviewer name recorded in review.json")
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root for relative paths")
    return parser.parse_args(_script_args(argv))


def main(argv: list[str] | None = None) -> Path:
    args = parse_args(argv)
    path = write_review_log(
        args.sweep_dir,
        winner=args.winner,
        promising=args.promising,
        rejects=_key_value(args.reject),
        failure_anchors=args.failure_anchor,
        tags_by_tile=_tags(args.tag),
        next_action=args.next_action,
        next_note=args.next_note,
        reviewer=args.reviewer,
        root=args.root,
    )
    print(f"Wrote {path}")
    return path


if __name__ == "__main__":
    main()
