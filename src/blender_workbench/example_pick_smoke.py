from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from blender_workbench.artifact_fingerprint import FRESHNESS_STALE, FRESHNESS_UNVERIFIED, fingerprint_status
from blender_workbench.example_manifest import load_manifest, select_examples
from blender_workbench.sweep import PROTECTED_PROMOTION_ROLES, SweepVariant, select_variant, variants_from_sweep_metadata


DEFAULT_BLENDER = "/Applications/Blender.app/Contents/MacOS/Blender"
PREFERRED_DEFAULT_ROLES = ("candidate", "baseline")


@dataclass(frozen=True)
class PickSmokePlan:
    name: str
    script: str
    metadata: str
    pick: str | None
    pick_role: str | None
    command: tuple[str, ...]
    selected_json: str | None
    runnable: bool
    reason: str = ""
    status: str = ""
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class PickSmokeResult:
    name: str
    pick: str | None
    command: tuple[str, ...]
    selected_json: str | None
    ok: bool
    errors: tuple[str, ...] = ()


def _script_args(argv: list[str] | None = None) -> list[str]:
    values = list(sys.argv[1:] if argv is None else argv)
    if "--" in values:
        return values[values.index("--") + 1 :]
    return values


def safe_output_name(value: str) -> str:
    safe = "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in value)
    return safe.strip("_") or "selected"


def script_supports_pick(script_path: Path) -> bool:
    if not script_path.exists():
        return False
    text = script_path.read_text()
    return "--pick" in text and "render_selected_from_sweep" in text


def example_output_dir(example: dict[str, Any], root: Path) -> Path | None:
    outputs = example.get("outputs", [])
    for output in outputs:
        path = Path(output)
        if path.name == "metadata.json":
            return root / path.parent
    return None


def _metadata_output_status(example: dict[str, Any], root: Path, metadata: Path) -> str:
    expected_fingerprints = example.get("output_fingerprints", {})
    if not isinstance(expected_fingerprints, dict):
        expected_fingerprints = {}
    for output in example.get("outputs", []):
        output_path = root / output
        if output_path == metadata:
            return fingerprint_status(metadata, expected_fingerprints.get(output))
    return fingerprint_status(metadata)


def _raw_metadata_roles(metadata: Path) -> tuple[dict[str, str], bool]:
    payload = json.loads(metadata.read_text())
    roles: dict[str, str] = {}
    saw_role = False
    variants = payload.get("variants")
    if isinstance(variants, list):
        for item in variants:
            if isinstance(item, Mapping) and isinstance(item.get("name"), str):
                role = item.get("role")
                if isinstance(role, str) and role:
                    roles[item["name"]] = role
                    saw_role = True
    workflow = payload.get("workflow")
    handles = workflow.get("pick_handles") if isinstance(workflow, Mapping) else None
    if isinstance(handles, list):
        for item in handles:
            if isinstance(item, Mapping) and isinstance(item.get("name"), str):
                role = item.get("role")
                if isinstance(role, str) and role:
                    roles[item["name"]] = role
                    saw_role = True
    return roles, saw_role


def _looks_like_protected_role(variant: SweepVariant) -> bool:
    text = " ".join(str(value) for value in (variant.name, variant.label, *variant.tags) if value).lower()
    return "fail" in text or "failure" in text or "negative_control" in text


def _effective_role(variant: SweepVariant, raw_roles: dict[str, str]) -> str:
    raw_role = raw_roles.get(variant.name)
    if raw_role:
        return raw_role
    if _looks_like_protected_role(variant):
        return "failure_anchor"
    return variant.role


def _select_default_variant(variants: list[SweepVariant], raw_roles: dict[str, str]) -> SweepVariant | None:
    for preferred_role in PREFERRED_DEFAULT_ROLES:
        for variant in variants:
            if _effective_role(variant, raw_roles) == preferred_role:
                return variant
    for variant in variants:
        if _effective_role(variant, raw_roles) not in PROTECTED_PROMOTION_ROLES:
            return variant
    return None


def _ready_status(*, explicit_protected: bool, metadata_warnings: tuple[str, ...]) -> str:
    if explicit_protected:
        return "ready_explicit_protected_pick"
    if metadata_warnings:
        return "ready_unverified_metadata"
    return "ready"


def plan_pick_smoke(
    example: dict[str, Any],
    *,
    root: Path,
    blender: str = DEFAULT_BLENDER,
    hero_samples: int = 4,
    pick: str | None = None,
    allow_protected_default: bool = False,
) -> PickSmokePlan:
    name = example["name"]
    script = example["script"]
    script_path = root / script
    out_dir = example_output_dir(example, root)
    if not script_supports_pick(script_path):
        return PickSmokePlan(name, script, "", None, None, (), None, False, "example does not expose --pick promotion", "blocked")
    if out_dir is None:
        return PickSmokePlan(name, script, "", None, None, (), None, False, "manifest has no metadata output", "blocked")

    metadata = out_dir / "metadata.json"
    if not metadata.exists():
        return PickSmokePlan(
            name,
            script,
            str(metadata),
            None,
            None,
            (),
            None,
            False,
            "metadata.json is missing; render the sweep first",
            "blocked",
        )

    variants = variants_from_sweep_metadata(out_dir)
    raw_roles, saw_role = _raw_metadata_roles(metadata)
    warnings: list[str] = []
    metadata_status = _metadata_output_status(example, root, metadata)
    if metadata_status in {FRESHNESS_STALE, FRESHNESS_UNVERIFIED}:
        warnings.append(f"metadata output is {metadata_status}; regenerate the sweep before trusting default picks")
    if not saw_role:
        warnings.append("metadata has no role fields; treating it as stale and avoiding failure-looking defaults")
    if pick:
        selected = select_variant(variants, pick)
    else:
        selected = _select_default_variant(variants, raw_roles)
        if selected is None:
            if not allow_protected_default:
                return PickSmokePlan(
                    name,
                    script,
                    str(metadata),
                    None,
                    None,
                    (),
                    None,
                    False,
                    "only protected-role picks are available; pass --pick or --allow-protected-default after review",
                    "blocked_protected_default",
                    tuple(warnings),
                )
            selected = variants[0]
            warnings.append("default protected-role pick allowed by --allow-protected-default")
    selected_role = _effective_role(selected, raw_roles)
    explicit_protected = bool(pick and selected_role in PROTECTED_PROMOTION_ROLES)
    if explicit_protected:
        warnings.append(f"explicit protected-role pick requested: {selected.name} ({selected_role})")
    selected_json = out_dir / "selected" / safe_output_name(selected.name) / "selected.json"
    command = (
        blender,
        "--background",
        "--python",
        script,
        "--",
        "--pick",
        selected.name,
        "--hero-samples",
        str(hero_samples),
    )
    return PickSmokePlan(
        name,
        script,
        str(metadata),
        selected.name,
        selected_role,
        command,
        str(selected_json),
        True,
        status=_ready_status(explicit_protected=explicit_protected, metadata_warnings=tuple(warnings)),
        warnings=tuple(warnings),
    )


def pick_smoke_plans(
    *,
    root: Path | None = None,
    manifest_path: Path | None = None,
    names: list[str] | None = None,
    blender: str = DEFAULT_BLENDER,
    hero_samples: int = 4,
    pick: str | None = None,
    allow_protected_default: bool = False,
) -> list[PickSmokePlan]:
    root = (root or Path.cwd()).resolve()
    examples = select_examples(load_manifest(manifest_path, root=root), names)
    return [
        plan_pick_smoke(
            example,
            root=root,
            blender=blender,
            hero_samples=hero_samples,
            pick=pick,
            allow_protected_default=allow_protected_default,
        )
        for example in examples
        if script_supports_pick(root / example["script"]) or names
    ]


def _resolve_output(path_text: str, root: Path) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else root / path


def verify_selected_json(path: Path, *, root: Path, expected_pick: str | None = None) -> tuple[str, ...]:
    errors: list[str] = []
    if not path.exists():
        return (f"missing selected.json: {path}",)
    payload = json.loads(path.read_text())
    selected = payload.get("selected", {})
    selected_name = selected.get("name")
    if expected_pick and selected_name != expected_pick:
        errors.append(f"selected name {selected_name!r} did not match expected {expected_pick!r}")
    if not payload.get("source_sweep"):
        errors.append("selected.json is missing source_sweep provenance")
    result = payload.get("result", {})
    raw = result.get("raw")
    if not raw:
        errors.append("selected.json result is missing raw output")
    elif not _resolve_output(raw, root).exists():
        errors.append(f"raw output does not exist: {raw}")
    finished = result.get("finished")
    if finished and not _resolve_output(finished, root).exists():
        errors.append(f"finished output does not exist: {finished}")
    return tuple(errors)


def run_pick_smoke(
    plan: PickSmokePlan,
    *,
    root: Path | None = None,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> PickSmokeResult:
    root = (root or Path.cwd()).resolve()
    if not plan.runnable:
        return PickSmokeResult(plan.name, plan.pick, plan.command, plan.selected_json, False, (plan.reason,))
    completed = runner(plan.command, cwd=root, check=False)
    errors: list[str] = []
    if completed.returncode != 0:
        errors.append(f"command exited {completed.returncode}")
    if plan.selected_json:
        errors.extend(verify_selected_json(Path(plan.selected_json), root=root, expected_pick=plan.pick))
    else:
        errors.append("plan did not include selected_json")
    return PickSmokeResult(plan.name, plan.pick, plan.command, plan.selected_json, not errors, tuple(errors))


def render_missing_sweep(example: dict[str, Any], *, root: Path, runner: Callable[..., subprocess.CompletedProcess] = subprocess.run) -> None:
    command = shlex.split(example["command"])
    completed = runner(command, cwd=root, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"{example['name']} sweep command exited {completed.returncode}")


def format_plan_report(plans: list[PickSmokePlan]) -> str:
    lines = ["Example pick smoke plans:", ""]
    for plan in plans:
        status = plan.status or ("ready" if plan.runnable else "blocked")
        lines.append(f"- {plan.name}: {status}")
        if plan.pick:
            lines.append(f"  pick: {plan.pick}")
        if plan.pick_role:
            lines.append(f"  role: {plan.pick_role}")
        if plan.command:
            lines.append(f"  command: {shlex.join(plan.command)}")
        if plan.selected_json:
            lines.append(f"  selected_json: {plan.selected_json}")
        if plan.reason:
            lines.append(f"  reason: {plan.reason}")
        for warning in plan.warnings:
            lines.append(f"  warning: {warning}")
    return "\n".join(lines)


def format_result_report(results: list[PickSmokeResult]) -> str:
    lines = ["Example pick smoke results:", ""]
    for result in results:
        status = "ok" if result.ok else "failed"
        lines.append(f"- {result.name}: {status}")
        if result.pick:
            lines.append(f"  pick: {result.pick}")
        if result.selected_json:
            lines.append(f"  selected_json: {result.selected_json}")
        for error in result.errors:
            lines.append(f"  error: {error}")
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan or run cheap Blender smoke checks for example --pick promotion paths.")
    parser.add_argument("--manifest", type=Path, help="manifest path, default examples/manifest.json")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="repository root")
    parser.add_argument("--name", action="append", help="example name to smoke-test; repeat for multiple examples")
    parser.add_argument("--pick", help="explicit pick to use for every selected example; default first metadata variant")
    parser.add_argument("--allow-protected-default", action="store_true", help="allow a protected-role default when no safer pick exists")
    parser.add_argument("--hero-samples", type=int, default=4, help="low sample count for selected renders")
    parser.add_argument("--blender", default=DEFAULT_BLENDER, help="Blender executable path")
    parser.add_argument("--run", action="store_true", help="actually launch Blender and verify selected.json")
    parser.add_argument("--json", action="store_true", help="print machine-readable plan/result JSON")
    return parser.parse_args(_script_args(argv))


def main(argv: list[str] | None = None) -> list[PickSmokePlan] | list[PickSmokeResult]:
    args = parse_args(argv)
    root = args.root.resolve()
    plans = pick_smoke_plans(
        root=root,
        manifest_path=args.manifest,
        names=args.name,
        blender=args.blender,
        hero_samples=args.hero_samples,
        pick=args.pick,
        allow_protected_default=args.allow_protected_default,
    )
    if not args.run:
        if args.json:
            print(json.dumps([asdict(plan) for plan in plans], indent=2))
        else:
            print(format_plan_report(plans))
        return plans

    results = [run_pick_smoke(plan, root=root) for plan in plans]
    if args.json:
        print(json.dumps([asdict(result) for result in results], indent=2))
    else:
        print(format_result_report(results))
    if any(not result.ok for result in results):
        raise SystemExit(1)
    return results


if __name__ == "__main__":
    main()
