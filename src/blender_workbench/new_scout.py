from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path


BLENDER = "/Applications/Blender.app/Contents/MacOS/Blender"


@dataclass(frozen=True)
class ScoutPlanItem:
    path: str
    kind: str
    action: str
    rationale: str
    required: bool = True


@dataclass(frozen=True)
class ScoutPlan:
    name: str
    slug: str
    example_name: str
    docs_title: str
    kind: str
    promotion_applicable: bool
    selected_render_path: str | None
    manifest_entry: dict
    items: tuple[ScoutPlanItem, ...]


def scout_slug(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip()).strip("_").lower()
    if not text:
        raise ValueError("scout name cannot be empty")
    if text.endswith("_scout"):
        text = text.removesuffix("_scout")
    return text


def scout_example_name(slug: str) -> str:
    return f"{slug}_scout"


def _title_from_slug(slug: str) -> str:
    return " ".join(part.capitalize() for part in slug.split("_")) + " Scout"


def _asset_name(example_name: str) -> str:
    return example_name.replace("_", "-") + ".jpg"


def build_scout_plan(
    *,
    name: str,
    docs_title: str | None = None,
    kind: str = "recipe",
    promotion_applicable: bool = True,
) -> ScoutPlan:
    slug = scout_slug(name)
    example_name = scout_example_name(slug)
    title = docs_title or _title_from_slug(slug)
    docs_stem = example_name.replace("_", "-")
    selected_path = f"examples/output/{example_name}/selected/<pick>/selected.json" if promotion_applicable else None
    command = f"{BLENDER} --background --python examples/{example_name}.py"
    manifest_entry = {
        "name": example_name,
        "script": f"examples/{example_name}.py",
        "command": command,
        "required_capabilities": ["blender", "magick"],
        "cost": {
            "profile": "cycles_preview",
            "engine": "CYCLES",
            "runtime": "quick",
            "mode": "grid_scout",
            "requires_blender": True,
            "tile_count": 9,
            "tile_preset": "auto_tiny_grid",
            "reuse_outputs": True,
        },
        "outputs": [
            f"examples/output/{example_name}/metadata.json",
            f"examples/output/{example_name}/contact_sheet.png",
        ],
        "prerequisites": [],
        "docs_asset": f"docs/assets/{_asset_name(example_name)}",
    }
    items = [
        ScoutPlanItem(
            path=f"src/blender_workbench/recipes/{slug}.py",
            kind="recipe_module",
            action="create",
            rationale="settings object, variants helper, and build_scene(settings) live here",
        ),
        ScoutPlanItem(
            path=f"examples/{example_name}.py",
            kind="example_script",
            action="create",
            rationale="renders the cheap grid and exposes selected-render promotion",
        ),
        ScoutPlanItem(
            path=f"tests/test_{slug}.py",
            kind="test",
            action="create",
            rationale="covers variants and scaffolded paths without launching Blender",
        ),
        ScoutPlanItem(
            path=f"docs/{docs_stem}.md",
            kind="docs",
            action="create",
            rationale="records source prompt, axes, failure anchors, and promotion guidance",
        ),
        ScoutPlanItem(
            path=f"docs/assets/{_asset_name(example_name)}",
            kind="docs_asset",
            action="generate",
            rationale="expected contact-sheet preview for docs and manifest preflight",
        ),
        ScoutPlanItem(
            path="examples/manifest.json",
            kind="manifest_entry",
            action="update",
            rationale="adds command, required capabilities, outputs, docs asset, and cost bucket",
        ),
        ScoutPlanItem(
            path="README.md",
            kind="readme",
            action="update",
            rationale="adds the scout to the visible example menu",
        ),
    ]
    if promotion_applicable:
        items.append(
            ScoutPlanItem(
                path=selected_path or "",
                kind="selected_render",
                action="create_via_pick",
                rationale="selected.json must prove the picked tile was promoted before scene reuse",
            )
        )
    else:
        items.append(
            ScoutPlanItem(
                path=f"examples/output/{example_name}/metadata.json",
                kind="selected_render",
                action="not_applicable",
                rationale="promotion was explicitly disabled for this scout plan",
                required=False,
            )
        )
    return ScoutPlan(
        name=name,
        slug=slug,
        example_name=example_name,
        docs_title=title,
        kind=kind,
        promotion_applicable=promotion_applicable,
        selected_render_path=selected_path,
        manifest_entry=manifest_entry,
        items=tuple(items),
    )


def format_scout_plan(plan: ScoutPlan) -> str:
    lines = [
        f"New scout scaffold: {plan.example_name}",
        "",
        f"- title: {plan.docs_title}",
        f"- kind: {plan.kind}",
        f"- promotion: {'--pick selected render required' if plan.promotion_applicable else 'not applicable by request'}",
        "",
        "Checklist:",
        "",
    ]
    for item in plan.items:
        marker = "required" if item.required else "optional"
        lines.append(f"- [{marker}] {item.action} {item.kind}: `{item.path}`")
        lines.append(f"  {item.rationale}")
    lines.extend(
        [
            "",
            "Manifest entry:",
            "",
            "```json",
            json.dumps(plan.manifest_entry, indent=2),
            "```",
        ]
    )
    if plan.promotion_applicable:
        lines.extend(
            [
                "",
                "Promotion command template:",
                "",
                "```bash",
                f"{BLENDER} --background --python examples/{plan.example_name}.py -- --pick {{pick}}",
                "```",
            ]
        )
    return "\n".join(lines)


def _settings_class(slug: str) -> str:
    return "".join(part.capitalize() for part in slug.split("_")) + "Settings"


def _camera_const(slug: str) -> str:
    return slug.upper() + "_CAMERA"


def _recipe_template(plan: ScoutPlan) -> str:
    settings_class = _settings_class(plan.slug)
    camera_const = _camera_const(plan.slug)
    return f'''from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from blender_workbench.sweep import SweepVariant


{camera_const} = "{plan.slug}_camera"


@dataclass(frozen=True)
class {settings_class}:
    scale: float = 1.0
    intensity: float = 1.0


def coerce_{plan.slug}_settings(settings: {settings_class} | Mapping[str, Any] | None = None) -> {settings_class}:
    if isinstance(settings, {settings_class}):
        return settings
    data = dataclasses.asdict({settings_class}())
    if settings:
        data.update({{key: value for key, value in dict(settings).items() if key in data}})
    return {settings_class}(**data)


def {plan.slug}_variants(prefix: str = "{plan.slug}") -> list[SweepVariant]:
    return [
        SweepVariant(f"{{prefix}}_base", dataclasses.asdict({settings_class}()), label="base"),
        SweepVariant(f"{{prefix}}_wide", {{"scale": 1.35, "intensity": 0.85}}, label="wide"),
        SweepVariant(
            f"{{prefix}}_overdone",
            {{"scale": 1.85, "intensity": 1.65}},
            label="overdone",
            role="failure_anchor",
            note="deliberate too-far anchor",
        ),
    ]


def build_{plan.slug}_scene(settings: {settings_class} | Mapping[str, Any] | None = None) -> None:
    """Build the scene for one scaffolded variant.

    Replace this placeholder with the actual Blender objects, camera, and lights.
    """
    _settings = coerce_{plan.slug}_settings(settings)
    raise NotImplementedError("Fill in {plan.docs_title} scene construction before rendering")
'''


def _example_template(plan: ScoutPlan) -> str:
    camera_const = _camera_const(plan.slug)
    return f'''from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from blender_workbench.presets import RENDER_PRESETS, TILE_PRESETS
from blender_workbench.recipes.{plan.slug} import {camera_const}, build_{plan.slug}_scene, {plan.slug}_variants
from blender_workbench.sweep import render_selected_from_sweep, render_sweep


OUT = ROOT / "examples" / "output" / "{plan.example_name}"


def _script_args(argv: list[str] | None = None) -> list[str]:
    values = list(sys.argv[1:] if argv is None else argv)
    if "--" in values:
        return values[values.index("--") + 1 :]
    return values


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render {plan.docs_title}, or promote one picked tile.")
    parser.add_argument("--pick", help="variant name, label, or 1-based index to render with the hero profile")
    parser.add_argument("--hero-samples", type=int, default=96, help="Cycles samples for --pick")
    parser.add_argument("--save-blend", action="store_true", help="also save a selected .blend for GUI review")
    parser.add_argument("--export-blend-only", action="store_true", help="save the selected .blend and skip image rendering")
    args, _unknown = parser.parse_known_args(_script_args(argv))
    return args


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    variants = {plan.slug}_variants()
    if args.pick:
        config = replace(RENDER_PRESETS["hero_check"], samples=args.hero_samples, camera_name={camera_const})
        render_selected_from_sweep(
            sweep_dir=OUT,
            pick=args.pick,
            build_scene=build_{plan.slug}_scene,
            root=ROOT,
            config=config,
            postprocess=None,
            title="{plan.docs_title} Selected Render",
            notes=["Promoted after inspecting the {plan.docs_title} contact sheet."],
            source_sweep_dir=OUT,
            save_blend=args.save_blend or args.export_blend_only,
            render_image=not args.export_blend_only,
        )
        return

    config = replace(RENDER_PRESETS["cycles_preview"], camera_name={camera_const}, tile=TILE_PRESETS["auto_tiny_grid"])
    render_sweep(
        variants=variants,
        build_scene=build_{plan.slug}_scene,
        out_dir=OUT,
        root=ROOT,
        config=config,
        postprocess=None,
        title="{plan.docs_title}",
        notes=["Replace this scaffold note with the source prompt, visual intent, and known failure modes."],
        promotion_command="{BLENDER} --background --python examples/{plan.example_name}.py -- --pick {{pick}}",
        square=True,
    )


if __name__ == "__main__":
    main()
'''


def _test_template(plan: ScoutPlan) -> str:
    return f'''import unittest

from blender_workbench.recipes.{plan.slug} import {plan.slug}_variants


class {''.join(part.capitalize() for part in plan.slug.split('_'))}Tests(unittest.TestCase):
    def test_variants_include_failure_anchor(self):
        variants = {plan.slug}_variants()

        self.assertGreaterEqual(len(variants), 3)
        self.assertTrue(any(variant.role == "failure_anchor" for variant in variants))


if __name__ == "__main__":
    unittest.main()
'''


def _docs_template(plan: ScoutPlan) -> str:
    return f'''# {plan.docs_title}

Source prompt:

- TODO: link the PDF page range, local reference study, or media cue.

Scout contract:

- Render a cheap grid first.
- Keep one deliberate failure anchor.
- Promote one pick with `--pick` before copying settings into a larger scene.
- Add the generated contact sheet to `docs/assets/{_asset_name(plan.example_name)}`.
- Add or update the `examples/manifest.json` entry shown by `tools/new_scout.py`.
'''


def scaffold_file_contents(plan: ScoutPlan) -> dict[str, str]:
    return {
        f"src/blender_workbench/recipes/{plan.slug}.py": _recipe_template(plan),
        f"examples/{plan.example_name}.py": _example_template(plan),
        f"tests/test_{plan.slug}.py": _test_template(plan),
        f"docs/{plan.example_name.replace('_', '-')}.md": _docs_template(plan),
    }


def write_scout_scaffold(plan: ScoutPlan, *, root: Path, force: bool = False) -> tuple[str, ...]:
    written: list[str] = []
    for rel_path, content in scaffold_file_contents(plan).items():
        path = root / rel_path
        if path.exists() and not force:
            raise FileExistsError(f"{rel_path} already exists; pass force=True to overwrite")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        written.append(rel_path)
    return tuple(written)


def plan_to_jsonable(plan: ScoutPlan) -> dict:
    payload = asdict(plan)
    payload["items"] = [asdict(item) for item in plan.items]
    return payload
