from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from blender_workbench.postprocess import postprocess_look_variants, render_postprocess_sweep
from blender_workbench.presets import TILE_PRESETS


DEFAULT_SOURCE = ROOT / "examples" / "output" / "terrain_environment_scout" / "selected" / "terrain_relief_p2" / "terrain_relief_p2.hero.raw.png"
OUT = ROOT / "examples" / "output" / "postprocess_look_scout"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a contact sheet of postprocess looks from one raw image.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="raw image to process")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if not args.source.exists():
        raise FileNotFoundError(
            f"{args.source} does not exist. Run: "
            "/Applications/Blender.app/Contents/MacOS/Blender --background --python "
            "examples/terrain_environment_scout.py -- --pick terrain_relief_p2"
        )

    render_postprocess_sweep(
        raw_image=args.source,
        variants=postprocess_look_variants(),
        out_dir=OUT,
        root=ROOT,
        tile=TILE_PRESETS["auto_square_moodboard"],
        title="Postprocess Look Scout",
        notes=[
            "One source render, many finishing looks: glow, contrast, saturation, warmth, and vignette.",
            "Inspired by BlenderArt compositing/finishing prompts.",
        ],
        square=True,
    )


if __name__ == "__main__":
    main()
