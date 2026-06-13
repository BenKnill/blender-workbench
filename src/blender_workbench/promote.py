from __future__ import annotations

import argparse
import importlib
import json
import sys
from collections.abc import Callable, Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

from blender_workbench.presets import RENDER_PRESETS
from blender_workbench.review_log import selected_pick_from_review
from blender_workbench.sweep import (
    RenderConfig,
    RenderResult,
    SweepVariant,
    normalize_procedural_controls,
    postprocess_glow_contrast,
    render_selected_variant,
    select_variant,
)


def _script_args(argv: list[str] | None = None) -> list[str]:
    values = list(sys.argv[1:] if argv is None else argv)
    if "--" in values:
        return values[values.index("--") + 1 :]
    return values


def safe_variant_name(value: str | int) -> str:
    text = str(value)
    return "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in text).strip("_") or "pick"


def metadata_path_for_sweep(sweep: Path) -> Path:
    path = Path(sweep)
    if path.is_dir():
        path = path / "metadata.json"
    return path


def load_sweep_metadata(sweep: Path) -> dict[str, Any]:
    path = metadata_path_for_sweep(sweep)
    if not path.exists():
        raise FileNotFoundError(path)
    metadata = json.loads(path.read_text())
    variants = metadata.get("variants")
    if not isinstance(variants, list):
        raise ValueError(f"{path} does not contain a variants list")
    return metadata


def variants_from_metadata(metadata: dict[str, Any]) -> list[SweepVariant]:
    variants: list[SweepVariant] = []
    for index, entry in enumerate(metadata.get("variants", []), start=1):
        if not isinstance(entry, dict):
            raise ValueError(f"Variant entry {index} is not an object")
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(f"Variant entry {index} is missing a name")
        settings = entry.get("settings", {})
        variants.append(
            SweepVariant(
                name=name,
                label=entry.get("label"),
                note=entry.get("note"),
                settings=settings,
                role=entry.get("role") or "candidate",
                tags=entry.get("tags") or (),
                replicate_of=entry.get("replicate_of") if isinstance(entry.get("replicate_of"), str) else None,
                replicate_index=entry.get("replicate_index") if isinstance(entry.get("replicate_index"), int) else None,
                procedural_controls=normalize_procedural_controls(
                    entry.get("procedural_controls") if isinstance(entry.get("procedural_controls"), dict) else None
                ),
            )
        )
    return variants


def load_sweep_variants(sweep: Path) -> list[SweepVariant]:
    return variants_from_metadata(load_sweep_metadata(sweep))


def select_metadata_variant(sweep: Path, pick: str | int) -> SweepVariant:
    return select_variant(load_sweep_variants(sweep), pick)


def import_recipe_callable(spec: str) -> Callable[[Any], None]:
    module_name, sep, attr_path = spec.partition(":")
    if not sep or not module_name or not attr_path:
        raise ValueError("Recipe must be written as module:callable")
    target: Any = importlib.import_module(module_name)
    for attr in attr_path.split("."):
        target = getattr(target, attr)
    if not callable(target):
        raise TypeError(f"{spec} is not callable")
    return target


def promote_from_metadata(
    *,
    sweep_dir: Path,
    pick: str | int | None = None,
    build_scene: Callable[[Any], None],
    out_dir: Path | None = None,
    root: Path | None = None,
    config: RenderConfig | None = None,
    camera_name: str | None = None,
    hero_samples: int | None = None,
    postprocess: Callable[[Path, Path], bool] | None = None,
    title: str = "Selected Blender Render",
    notes: list[str] | None = None,
    handoff_notes: Mapping[str, Any] | None = None,
    save_blend: bool = False,
    render_image: bool = True,
    allow_anchor_promotion: bool = False,
) -> RenderResult:
    source_sweep_dir = metadata_path_for_sweep(sweep_dir).parent
    variants = load_sweep_variants(sweep_dir)
    if pick is None:
        pick = selected_pick_from_review(source_sweep_dir)
        if pick is None:
            raise ValueError(f"No pick provided and {source_sweep_dir / 'review.json'} has no promotable winner")
    selected = select_variant(variants, pick)
    cfg = config or RENDER_PRESETS["hero_check"]
    if camera_name is not None:
        cfg = replace(cfg, camera_name=camera_name)
    if hero_samples is not None:
        cfg = replace(cfg, samples=hero_samples)

    root = root or Path.cwd()
    out_dir = out_dir or source_sweep_dir / "selected" / safe_variant_name(selected.name)
    return render_selected_variant(
        variants=variants,
        pick=selected.name,
        build_scene=build_scene,
        out_dir=out_dir,
        root=root,
        config=cfg,
        postprocess=postprocess,
        title=title,
        notes=notes
        or [
            "Promoted from an existing sweep metadata file.",
            "The full contact sheet was not rerendered for this selected pass.",
        ],
        handoff_notes=handoff_notes,
        source_sweep_dir=source_sweep_dir,
        save_blend=save_blend,
        render_image=render_image,
        allow_anchor_promotion=allow_anchor_promotion,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Promote one existing sweep tile from metadata.json into a selected render.")
    parser.add_argument("--sweep", type=Path, required=True, help="sweep output directory or metadata.json path")
    parser.add_argument("--pick", help="variant name, label, or 1-based index; defaults to review.json winner")
    parser.add_argument("--recipe", required=True, help="scene builder callable, written as module:callable")
    parser.add_argument("--out", type=Path, help="selected-render output directory")
    parser.add_argument("--root", type=Path, help="repository/root path for relative metadata paths")
    parser.add_argument("--camera-name", help="camera object name to use for the hero render")
    parser.add_argument("--hero-samples", type=int, help="override hero render samples")
    parser.add_argument("--title", default="Selected Blender Render", help="README title for the selected render")
    parser.add_argument("--postprocess-glow", action="store_true", help="apply the workbench glow/contrast postprocess after rendering")
    parser.add_argument("--save-blend", action="store_true", help="also save selected/<pick>/<pick>.blend for GUI review")
    parser.add_argument("--export-blend-only", action="store_true", help="save the selected .blend and skip image rendering")
    parser.add_argument("--handoff-preserve", action="append", default=[], help="constraint to keep legible in handoff.md")
    parser.add_argument("--handoff-improve-after", action="append", default=[], help="detail to refine after structure works")
    parser.add_argument("--handoff-failure-mode", action="append", default=[], help="known failure mode to carry into handoff.md")
    parser.add_argument(
        "--handoff-reference",
        action="append",
        default=[],
        help="reference target path or cue to record in prompt_card.json",
    )
    parser.add_argument("--allow-anchor-promotion", action="store_true", help="allow deliberate failure/negative-control picks")
    return parser.parse_args(_script_args(argv))


def main(argv: list[str] | None = None) -> RenderResult:
    args = parse_args(argv)
    result = promote_from_metadata(
        sweep_dir=args.sweep,
        pick=args.pick,
        build_scene=import_recipe_callable(args.recipe),
        out_dir=args.out,
        root=args.root,
        camera_name=args.camera_name,
        hero_samples=args.hero_samples,
        postprocess=postprocess_glow_contrast if args.postprocess_glow else None,
        title=args.title,
        handoff_notes={
            "preserve": args.handoff_preserve,
            "improve_after": args.handoff_improve_after,
            "failure_modes": args.handoff_failure_mode,
            "reference_targets": args.handoff_reference,
        },
        save_blend=args.save_blend or args.export_blend_only,
        render_image=not args.export_blend_only,
        allow_anchor_promotion=args.allow_anchor_promotion,
    )
    print(f"Promoted {result.name}: {result.finished or result.raw or result.blend}")
    return result


if __name__ == "__main__":
    main()
