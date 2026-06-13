from __future__ import annotations

import importlib.util
import platform
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence


DEFAULT_BLENDER_PATH = Path("/Applications/Blender.app/Contents/MacOS/Blender")

DEFAULT_COMMANDS = (
    "python3",
    "blender",
    "magick",
    "ffmpeg",
    "yt-dlp",
    "qlmanage",
    "sips",
    "mdls",
    "swift",
    "pdftotext",
    "pdfinfo",
    "pdftoppm",
    "gs",
)

DEFAULT_PYTHON_MODULES = ("blender_workbench", "pypdf", "PyPDF2", "pdfplumber", "fitz")

VERSION_ARGS = {
    "python3": ("--version",),
    "blender": ("--version",),
    "magick": ("-version",),
    "ffmpeg": ("-version",),
    "yt-dlp": ("--version",),
    "swift": ("--version",),
    "pdftotext": ("-v",),
    "pdfinfo": ("-v",),
    "pdftoppm": ("-v",),
    "gs": ("--version",),
}

REQUIREMENT_TOOL_MAP = {
    "python": ("python3",),
    "python3": ("python3",),
    "blender": ("blender",),
    "magick": ("magick",),
    "postprocess_only": ("python3", "magick"),
    "video_reference": ("ffmpeg", "yt-dlp"),
    "pdf_triage": ("magick", "swift"),
}


@dataclass(frozen=True)
class CommandStatus:
    name: str
    available: bool
    path: str | None = None
    version: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class ModuleStatus:
    name: str
    available: bool


@dataclass(frozen=True)
class CapabilityRule:
    name: str
    required_tools: tuple[str, ...] = ()
    any_tool_groups: tuple[tuple[str, ...], ...] = ()
    required_modules: tuple[str, ...] = ()
    optional_tools: tuple[str, ...] = ()
    optional_modules: tuple[str, ...] = ()
    note: str = ""


@dataclass(frozen=True)
class CapabilityStatus:
    name: str
    status: str
    required_tools: tuple[str, ...]
    any_tool_groups: tuple[tuple[str, ...], ...]
    required_modules: tuple[str, ...]
    missing_tools: tuple[str, ...]
    missing_any_tool_groups: tuple[tuple[str, ...], ...]
    missing_modules: tuple[str, ...]
    optional_tools: tuple[str, ...]
    optional_modules: tuple[str, ...]
    note: str


CAPABILITY_RULES = (
    CapabilityRule(
        "example_wrappers",
        required_tools=("python3",),
        required_modules=("blender_workbench",),
        note="Python wrappers import this checkout before launching example commands.",
    ),
    CapabilityRule(
        "blender",
        required_tools=("blender",),
        optional_tools=("magick",),
        note="Blender command availability without starting a render.",
    ),
    CapabilityRule(
        "postprocess_only",
        required_tools=("python3", "magick"),
        note="ImageMagick-backed finishing-look and contact-sheet workflows.",
    ),
    CapabilityRule(
        "video_reference",
        required_tools=("ffmpeg", "yt-dlp"),
        note="Video frame extraction and remote reference capture helpers.",
    ),
    CapabilityRule(
        "pdf_triage",
        required_tools=("magick",),
        any_tool_groups=(("swift", "pdftoppm", "qlmanage"),),
        optional_tools=("pdftotext", "pdfinfo", "gs", "sips", "mdls"),
        optional_modules=("pypdf", "PyPDF2", "pdfplumber", "fitz"),
        note="At least one PDF page or thumbnail backend plus ImageMagick for sheets.",
    ),
)


def _dedupe(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def expand_required_tools(requirements: Sequence[str]) -> tuple[str, ...]:
    tools: list[str] = []
    for requirement in requirements:
        tools.extend(REQUIREMENT_TOOL_MAP.get(requirement, (requirement,)))
    return _dedupe(tools)


def resolve_tool_path(
    tool: str,
    *,
    which: Callable[[str], str | None] = shutil.which,
    path_exists: Callable[[Path], bool] | None = None,
    blender_path: Path = DEFAULT_BLENDER_PATH,
) -> str | None:
    path_exists = path_exists or (lambda path: path.exists())
    if tool == "python":
        tool = "python3"
    if tool == "blender":
        if path_exists(blender_path):
            return str(blender_path)
        return which("blender")
    return which(tool)


def _run_version(cmd: list[str]) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            cmd,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=8,
        )
        return True, completed.stdout.strip() or completed.stderr.strip() or "ok"
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        stderr = getattr(exc, "stderr", "") or str(exc)
        return False, str(stderr).strip()


def _first_line(text: str | None) -> str | None:
    if not text:
        return None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def probe_command(
    tool: str,
    *,
    which: Callable[[str], str | None] = shutil.which,
    path_exists: Callable[[Path], bool] | None = None,
    runner: Callable[[list[str]], tuple[bool, str]] = _run_version,
    check_version: bool = True,
) -> CommandStatus:
    path = resolve_tool_path(tool, which=which, path_exists=path_exists)
    if not path:
        return CommandStatus(name=tool, available=False)
    version = None
    error = None
    if check_version and tool in VERSION_ARGS:
        ok, detail = runner([path, *VERSION_ARGS[tool]])
        if ok:
            version = _first_line(detail)
        else:
            error = _first_line(detail)
    return CommandStatus(name=tool, available=True, path=path, version=version, error=error)


def probe_module(name: str, *, module_available: Callable[[str], bool] | None = None) -> ModuleStatus:
    module_available = module_available or (lambda module_name: importlib.util.find_spec(module_name) is not None)
    return ModuleStatus(name=name, available=module_available(name))


def evaluate_capability_rule(
    rule: CapabilityRule,
    *,
    commands: dict[str, dict[str, Any]],
    modules: dict[str, dict[str, Any]],
) -> CapabilityStatus:
    missing_tools = tuple(tool for tool in rule.required_tools if not commands.get(tool, {}).get("available"))
    missing_any_tool_groups = tuple(
        group for group in rule.any_tool_groups if not any(commands.get(tool, {}).get("available") for tool in group)
    )
    missing_modules = tuple(module for module in rule.required_modules if not modules.get(module, {}).get("available"))
    status = "ready"
    if missing_tools or missing_any_tool_groups or missing_modules:
        status = "blocked_missing_tool"
    return CapabilityStatus(
        name=rule.name,
        status=status,
        required_tools=rule.required_tools,
        any_tool_groups=rule.any_tool_groups,
        required_modules=rule.required_modules,
        missing_tools=missing_tools,
        missing_any_tool_groups=missing_any_tool_groups,
        missing_modules=missing_modules,
        optional_tools=rule.optional_tools,
        optional_modules=rule.optional_modules,
        note=rule.note,
    )


def render_engine_report(blender_available: bool) -> dict[str, dict[str, str]]:
    status = "ready" if blender_available else "blocked_missing_tool"
    note = "requires Blender binary; scene-level engine validation belongs to Blender sanity checks"
    return {
        engine: {"status": status, "note": note}
        for engine in ("BLENDER_WORKBENCH", "EEVEE", "EEVEE_NEXT", "CYCLES")
    }


def collect_capability_report(
    *,
    which: Callable[[str], str | None] = shutil.which,
    path_exists: Callable[[Path], bool] | None = None,
    runner: Callable[[list[str]], tuple[bool, str]] = _run_version,
    module_available: Callable[[str], bool] | None = None,
    check_versions: bool = True,
) -> dict[str, Any]:
    rule_tools: list[str] = []
    rule_modules: list[str] = []
    for rule in CAPABILITY_RULES:
        rule_tools.extend(rule.required_tools)
        rule_tools.extend(rule.optional_tools)
        for group in rule.any_tool_groups:
            rule_tools.extend(group)
        rule_modules.extend(rule.required_modules)
        rule_modules.extend(rule.optional_modules)
    command_names = _dedupe((*DEFAULT_COMMANDS, *rule_tools))
    module_names = _dedupe((*DEFAULT_PYTHON_MODULES, *rule_modules))

    commands = {
        name: asdict(
            probe_command(
                name,
                which=which,
                path_exists=path_exists,
                runner=runner,
                check_version=check_versions,
            )
        )
        for name in command_names
    }
    modules = {name: asdict(probe_module(name, module_available=module_available)) for name in module_names}
    groups = {rule.name: asdict(evaluate_capability_rule(rule, commands=commands, modules=modules)) for rule in CAPABILITY_RULES}
    status = "ready" if all(group["status"] == "ready" for group in groups.values()) else "blocked_missing_tool"
    return {
        "schema": 1,
        "platform": platform.platform(),
        "status": status,
        "commands": commands,
        "python_modules": modules,
        "capability_groups": groups,
        "render_engines": render_engine_report(bool(commands["blender"]["available"])),
    }


def format_capability_report(report: dict[str, Any]) -> str:
    lines = ["Workbench doctor:", "", f"Overall: {report['status']}", "", "Capability groups:"]
    for name, group in report["capability_groups"].items():
        lines.append(f"- {name}: {group['status']}")
        if group.get("missing_tools"):
            lines.append(f"  missing tools: {', '.join(group['missing_tools'])}")
        for any_group in group.get("missing_any_tool_groups", []):
            lines.append(f"  missing one of: {', '.join(any_group)}")
        if group.get("missing_modules"):
            lines.append(f"  missing modules: {', '.join(group['missing_modules'])}")
        if group.get("note"):
            lines.append(f"  note: {group['note']}")

    lines.extend(["", "Commands:"])
    for name, command in report["commands"].items():
        if command["available"]:
            detail = command["path"] or "available"
            if command.get("version"):
                detail = f"{detail} ({command['version']})"
            elif command.get("error"):
                detail = f"{detail} (version check failed: {command['error']})"
        else:
            detail = "missing"
        lines.append(f"- {name}: {detail}")

    lines.extend(["", "Python modules:"])
    for name, module in report["python_modules"].items():
        lines.append(f"- {name}: {'available' if module['available'] else 'missing'}")

    lines.extend(["", "Render engines:"])
    for name, engine in report["render_engines"].items():
        lines.append(f"- {name}: {engine['status']}")
    return "\n".join(lines)
