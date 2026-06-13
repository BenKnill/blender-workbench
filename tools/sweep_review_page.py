from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from blender_workbench.review_page import write_review_page


def _script_args(argv: list[str] | None = None) -> list[str]:
    values = list(sys.argv[1:] if argv is None else argv)
    if "--" in values:
        return values[values.index("--") + 1 :]
    return values


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write a static review.html page for an existing sweep directory.")
    parser.add_argument("sweep_dir", type=Path, help="directory containing metadata.json and sweep images")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="repository root for metadata-relative image paths")
    parser.add_argument("--metadata", type=Path, help="metadata path, default SWEEP_DIR/metadata.json")
    parser.add_argument("--out", type=Path, help="output HTML path, default SWEEP_DIR/review.html")
    return parser.parse_args(_script_args(argv))


def main(argv: list[str] | None = None) -> Path:
    args = parse_args(argv)
    path = write_review_page(args.sweep_dir, root=args.root, metadata_path=args.metadata, out_path=args.out)
    print(f"Wrote {path}")
    return path


if __name__ == "__main__":
    main()
