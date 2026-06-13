from __future__ import annotations

import dataclasses
import json
import math
import shlex
import shutil
import subprocess
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .artifact_fingerprint import (
    fingerprint_matches,
    fingerprint_status,
    make_artifact_fingerprint,
    render_cache_fingerprint,
    write_fingerprint_record,
)
from .handoff import write_handoff_card
from .image_diagnostics import analyze_sweep_images, format_diagnostics_readme, write_diagnostics
from .review_page import write_review_page


VARIANT_ROLES = (
    "candidate",
    "baseline",
    "failure_anchor",
    "negative_control",
    "aesthetic_extreme",
    "reference_attempt",
)
PROTECTED_PROMOTION_ROLES = ("failure_anchor", "negative_control")
PROCEDURAL_SETTING_KEYS = (
    "seed",
    "variation_seed",
    "noise_seed",
    "noise_phase",
    "texture_offset",
    "texture_phase",
)


def normalize_variant_role(role: str | None) -> str:
    value = role or "candidate"
    if value not in VARIANT_ROLES:
        allowed = ", ".join(VARIANT_ROLES)
        raise ValueError(f"Unknown variant role {value!r}; expected one of: {allowed}")
    return value


def normalize_variant_tags(tags: Iterable[str] | None) -> tuple[str, ...]:
    if tags is None:
        return ()
    return tuple(dict.fromkeys(str(tag) for tag in tags if str(tag)))


def normalize_procedural_controls(controls: Mapping[str, Any] | None) -> dict[str, Any]:
    if controls is None:
        return {}
    return {str(key): value for key, value in dict(controls).items() if str(key)}


@dataclass(frozen=True)
class SweepVariant:
    name: str
    settings: Any
    label: str | None = None
    note: str | None = None
    role: str = "candidate"
    tags: tuple[str, ...] = ()
    replicate_of: str | None = None
    replicate_index: int | None = None
    procedural_controls: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "role", normalize_variant_role(self.role))
        object.__setattr__(self, "tags", normalize_variant_tags(self.tags))
        object.__setattr__(self, "procedural_controls", normalize_procedural_controls(self.procedural_controls))
        if self.replicate_index is not None and self.replicate_index < 1:
            raise ValueError("replicate_index must be 1-based when provided")


@dataclass(frozen=True)
class RenderResult:
    name: str
    raw: str | None
    finished: str | None
    settings: Any
    label: str | None = None
    note: str | None = None
    role: str = "candidate"
    tags: tuple[str, ...] = ()
    replicate_of: str | None = None
    replicate_index: int | None = None
    procedural_controls: Mapping[str, Any] = field(default_factory=dict)
    blend: str | None = None
    open_blend_command: str | None = None
    render_skipped: bool = False
    engine: str | None = None
    camera_name: str | None = None
    build_seconds: float | None = None
    render_seconds: float | None = None
    postprocess_seconds: float | None = None
    skipped_existing: bool = False
    cache_status: str | None = None
    cache_warning: str | None = None
    fingerprint: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "role", normalize_variant_role(self.role))
        object.__setattr__(self, "tags", normalize_variant_tags(self.tags))
        object.__setattr__(self, "procedural_controls", normalize_procedural_controls(self.procedural_controls))
        if self.replicate_index is not None and self.replicate_index < 1:
            raise ValueError("replicate_index must be 1-based when provided")


@dataclass(frozen=True)
class ReferenceTarget:
    path: str | None = None
    url: str | None = None
    source_type: str = "image"
    caption: str | None = None
    crop: str | None = None
    frame: str | int | None = None
    page: str | int | None = None
    notes: tuple[str, ...] = ()
    match: tuple[str, ...] = ()


@dataclass(frozen=True)
class TileSpec:
    width: int = 112
    height: int = 112
    columns: int | None = None
    label_height: int = 14
    background: str = "black"
    show_notes: bool = False
    show_labels: bool = True
    label_max_chars: int | None = 12
    label_point_size: int | None = None

    @classmethod
    def hero_pair(cls) -> "TileSpec":
        return cls(width=360, height=360, columns=2, label_height=28, show_notes=True, label_max_chars=42)

    @classmethod
    def balanced_grid(cls) -> "TileSpec":
        return cls(width=160, height=160, columns=None, label_height=18, label_max_chars=18)

    @classmethod
    def micro_grid(cls, columns: int = 8) -> "TileSpec":
        return cls(width=104, height=104, columns=columns, label_height=14, label_max_chars=12)

    @classmethod
    def auto_micro_grid(cls) -> "TileSpec":
        return cls(width=104, height=104, columns=None, label_height=14, label_max_chars=12)

    @classmethod
    def tiny_grid(cls, columns: int = 10) -> "TileSpec":
        return cls(width=88, height=88, columns=columns, label_height=12, label_max_chars=14)

    @classmethod
    def auto_tiny_grid(cls) -> "TileSpec":
        return cls(width=88, height=88, columns=None, label_height=12, label_max_chars=14)

    @classmethod
    def square_moodboard(cls, columns: int = 5) -> "TileSpec":
        return cls(width=176, height=176, columns=columns, label_height=20, label_max_chars=20)

    @classmethod
    def auto_square_moodboard(cls) -> "TileSpec":
        return cls(width=176, height=176, columns=None, label_height=20, label_max_chars=20)

    @classmethod
    def filmstrip(cls, columns: int = 6) -> "TileSpec":
        return cls(width=280, height=170, columns=columns, label_height=24, label_max_chars=32)

    def columns_for_count(self, count: int) -> int:
        if self.columns is not None:
            return max(1, self.columns)
        return max(1, math.ceil(math.sqrt(max(1, count))))

    def with_auto_columns(self) -> "TileSpec":
        return dataclasses.replace(self, columns=None)

    def without_labels(self) -> "TileSpec":
        return dataclasses.replace(self, show_labels=False, label_height=0)


@dataclass(frozen=True)
class RenderConfig:
    resolution_x: int = 960
    resolution_y: int = 630
    engine: str = "CYCLES"
    samples: int = 72
    use_denoising: bool = True
    use_persistent_data: bool = True
    max_bounces: int | None = 6
    transparent_max_bounces: int | None = 16
    view_transform: str = "Filmic"
    look: str = "High Contrast"
    exposure: float = 0.0
    gamma: float = 1.0
    reuse_existing: bool = False
    camera_name: str | None = None
    tile: TileSpec = field(default_factory=TileSpec)

    @classmethod
    def shape_scout(cls) -> "RenderConfig":
        return cls(
            resolution_x=520,
            resolution_y=340,
            engine="BLENDER_WORKBENCH",
            samples=1,
            use_denoising=False,
            transparent_max_bounces=None,
            view_transform="Standard",
            look="Medium High Contrast",
            tile=TileSpec.micro_grid(columns=8),
        )

    @classmethod
    def material_scout(cls) -> "RenderConfig":
        return cls(
            resolution_x=640,
            resolution_y=420,
            engine="EEVEE",
            samples=12,
            use_denoising=False,
            transparent_max_bounces=None,
            view_transform="Filmic",
            look="Medium High Contrast",
            tile=TileSpec.micro_grid(columns=6),
        )

    @classmethod
    def cycles_preview(cls) -> "RenderConfig":
        return cls(
            resolution_x=760,
            resolution_y=500,
            engine="CYCLES",
            samples=32,
            max_bounces=4,
            transparent_max_bounces=18,
            tile=TileSpec.balanced_grid(),
        )

    @classmethod
    def hero_check(cls) -> "RenderConfig":
        return cls(
            resolution_x=1280,
            resolution_y=840,
            engine="CYCLES",
            samples=96,
            max_bounces=8,
            transparent_max_bounces=24,
            tile=TileSpec.hero_pair(),
        )


def settings_to_jsonable(settings: Any) -> Any:
    if dataclasses.is_dataclass(settings):
        return dataclasses.asdict(settings)
    if isinstance(settings, Mapping):
        return dict(settings)
    if hasattr(settings, "__dict__"):
        return dict(settings.__dict__)
    return settings


def infer_procedural_controls(settings: Any) -> dict[str, Any]:
    """Return seed/phase-like fields already present in variant settings."""
    data = settings_to_jsonable(settings)
    if not isinstance(data, Mapping):
        return {}
    return {key: data[key] for key in PROCEDURAL_SETTING_KEYS if key in data}


def _variant_procedural_controls(variant: SweepVariant) -> dict[str, Any]:
    controls = infer_procedural_controls(variant.settings)
    controls.update(normalize_procedural_controls(variant.procedural_controls))
    return controls


def _settings_mapping_for_replicates(settings: Any) -> dict[str, Any]:
    data = settings_to_jsonable(settings)
    if not isinstance(data, Mapping):
        raise TypeError("procedural replicate variants require mapping or dataclass settings")
    return dict(data)


def _replicate_token(value: Any) -> str:
    text = str(value).replace("-", "m").replace(".", "p")
    safe = "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in text)
    return safe.strip("_") or "value"


def _procedural_text(controls: Mapping[str, Any], replicate_of: str | None = None, replicate_index: int | None = None) -> str:
    bits = [f"{key}={value}" for key, value in controls.items()]
    if replicate_of:
        bits.insert(0, f"replicate {replicate_index or '?'} of {replicate_of}")
    return ", ".join(bits)


def replicate_variants(
    base_variant: SweepVariant,
    *,
    seeds: Iterable[int] = (0, 1, 2),
    phases: Iterable[float] | None = None,
    seed_field: str = "variation_seed",
    phase_field: str = "noise_phase",
    role: str = "candidate",
    tags: Iterable[str] = ("robustness_replicate",),
) -> list[SweepVariant]:
    """Expand one picked variant into seed/phase robustness replicates.

    The original sweep stays untouched; each returned variant keeps the chosen
    settings and only overrides the requested procedural fields.
    """
    seed_values = list(seeds)
    phase_values = list(phases) if phases is not None else [None]
    if not seed_values:
        raise ValueError("replicate_variants requires at least one seed")
    if not phase_values:
        raise ValueError("replicate_variants requires at least one phase when phases are provided")

    base_settings = _settings_mapping_for_replicates(base_variant.settings)
    base_controls = _variant_procedural_controls(base_variant)
    replicate_tags = normalize_variant_tags((*base_variant.tags, *normalize_variant_tags(tags)))
    variants: list[SweepVariant] = []
    for seed in seed_values:
        for phase in phase_values:
            settings = dict(base_settings)
            controls = dict(base_controls)
            name_parts = [base_variant.name]
            if seed_field:
                settings[seed_field] = seed
                controls[seed_field] = seed
                name_parts.append(f"seed{_replicate_token(seed)}")
            if phase is not None and phase_field:
                settings[phase_field] = phase
                controls[phase_field] = phase
                name_parts.append(f"phase{_replicate_token(phase)}")
            variants.append(
                SweepVariant(
                    name="_".join(name_parts),
                    label=base_variant.label or base_variant.name,
                    settings=settings,
                    note=base_variant.note,
                    role=role,
                    tags=replicate_tags,
                    replicate_of=base_variant.name,
                    replicate_index=len(variants) + 1,
                    procedural_controls=controls,
                )
            )
    return variants


def grid_variants(
    row_values: Iterable[tuple[str, Mapping[str, Any]]],
    column_values: Iterable[tuple[str, Mapping[str, Any]]],
    *,
    base: Mapping[str, Any] | None = None,
    name_sep: str = "_",
    role: str = "candidate",
    tags: Iterable[str] | None = None,
) -> list[SweepVariant]:
    """Build row-major variants from row and column parameter overrides."""
    variants: list[SweepVariant] = []
    base_data = dict(base or {})
    for row_label, row_data in row_values:
        for col_label, col_data in column_values:
            data = dict(base_data)
            data.update(row_data)
            data.update(col_data)
            name = f"{row_label}{name_sep}{col_label}"
            variants.append(
                SweepVariant(
                    name=name,
                    label=name,
                    settings=data,
                    role=role,
                    tags=normalize_variant_tags(tags),
                )
            )
    return variants


def named_variants(
    cases: Mapping[str, Mapping[str, Any]] | Iterable[tuple[str, Mapping[str, Any]]],
    *,
    base: Mapping[str, Any] | None = None,
    prefix: str | None = None,
    note: str | None = None,
    role: str = "candidate",
    tags: Iterable[str] | None = None,
    roles: Mapping[str, str] | None = None,
    tags_by_name: Mapping[str, Iterable[str]] | None = None,
) -> list[SweepVariant]:
    """Build variants from already-named cases.

    This is the lightest path for moodboards and named explorations where a
    row/column grid would add ceremony instead of clarity.
    """
    case_items = cases.items() if isinstance(cases, Mapping) else cases
    variants: list[SweepVariant] = []
    base_data = dict(base or {})
    default_tags = normalize_variant_tags(tags)
    roles = roles or {}
    tags_by_name = tags_by_name or {}
    for label, settings in case_items:
        data = dict(base_data)
        data.update(settings)
        name = f"{prefix}_{label}" if prefix else label
        variant_tags = (*default_tags, *normalize_variant_tags(tags_by_name.get(label)))
        variants.append(
            SweepVariant(
                name=name,
                label=label,
                settings=data,
                note=note,
                role=roles.get(label, role),
                tags=variant_tags,
            )
        )
    return variants


def select_variant(variants: Iterable[SweepVariant], pick: str | int) -> SweepVariant:
    """Select a variant by 1-based index, exact name, or exact label."""
    variant_list = list(variants)
    if not variant_list:
        raise ValueError("Cannot select from an empty variant list")

    if isinstance(pick, int) or (isinstance(pick, str) and pick.isdigit()):
        index = int(pick)
        if 1 <= index <= len(variant_list):
            return variant_list[index - 1]
        raise ValueError(f"Variant index {index} is outside 1..{len(variant_list)}")

    matches = [variant for variant in variant_list if variant.name == pick]
    if not matches:
        matches = [variant for variant in variant_list if variant.label == pick]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError(f"Variant pick {pick!r} is ambiguous; use the full variant name")

    preview = ", ".join(variant.name for variant in variant_list[:8])
    suffix = "" if len(variant_list) <= 8 else f", ... ({len(variant_list)} total)"
    raise ValueError(f"Unknown variant {pick!r}. Available names: {preview}{suffix}")


def _relative_or_absolute(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _safe_output_name(value: str) -> str:
    safe = "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in value)
    return safe.strip("_") or "selected"


def _open_blend_command(blend_path: Path, root: Path) -> str:
    return f"open -a Blender {shlex.quote(_relative_or_absolute(blend_path, root))}"


def coerce_reference_targets(targets: Iterable[ReferenceTarget | Mapping[str, Any]] | None = None) -> tuple[ReferenceTarget, ...]:
    if not targets:
        return ()
    coerced: list[ReferenceTarget] = []
    for target in targets:
        if isinstance(target, ReferenceTarget):
            coerced.append(target)
            continue
        data = dict(target)
        for key in ("notes", "match"):
            value = data.get(key)
            if value is None:
                data[key] = ()
            elif isinstance(value, str):
                data[key] = (value,)
            else:
                data[key] = tuple(str(item) for item in value)
        coerced.append(ReferenceTarget(**data))
    return tuple(coerced)


def reference_targets_to_metadata(targets: Iterable[ReferenceTarget | Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [settings_to_jsonable(target) for target in coerce_reference_targets(targets)]


def _reference_target_path(target: ReferenceTarget, root: Path) -> Path | None:
    if not target.path:
        return None
    path = Path(target.path)
    return path if path.is_absolute() else root / path


def _local_reference_targets(targets: Iterable[ReferenceTarget], root: Path) -> list[tuple[ReferenceTarget, Path]]:
    local = []
    for target in targets:
        path = _reference_target_path(target, root)
        if path and path.exists():
            local.append((target, path))
    return local


def variants_from_sweep_metadata(sweep_dir: Path) -> list[SweepVariant]:
    """Rebuild pickable variants from a prior sweep's `metadata.json`.

    This is the durable path after visual inspection: render the grid, choose a
    tile from the artifact, then promote from the recorded settings rather than
    relying on a script to reconstruct the same variant list perfectly.
    """
    sweep_dir = Path(sweep_dir)
    metadata_path = sweep_dir / "metadata.json"
    payload = json.loads(metadata_path.read_text())
    variants = payload.get("variants")
    if not isinstance(variants, list):
        raise ValueError(f"{metadata_path} does not contain a variants list")

    rebuilt: list[SweepVariant] = []
    for index, item in enumerate(variants, start=1):
        if not isinstance(item, Mapping):
            raise ValueError(f"{metadata_path} variant {index} is not an object")
        name = item.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(f"{metadata_path} variant {index} is missing a name")
        if "settings" not in item:
            raise ValueError(f"{metadata_path} variant {name!r} is missing settings")
        label = item.get("label")
        note = item.get("note")
        tags = item.get("tags")
        rebuilt.append(
            SweepVariant(
                name=name,
                settings=item["settings"],
                label=label if isinstance(label, str) else None,
                note=note if isinstance(note, str) else None,
                role=normalize_variant_role(item.get("role")),
                tags=normalize_variant_tags(tags if isinstance(tags, (list, tuple)) else None),
                replicate_of=item.get("replicate_of") if isinstance(item.get("replicate_of"), str) else None,
                replicate_index=item.get("replicate_index") if isinstance(item.get("replicate_index"), int) else None,
                procedural_controls=normalize_procedural_controls(
                    item.get("procedural_controls") if isinstance(item.get("procedural_controls"), Mapping) else None
                ),
            )
        )
    return rebuilt


def _engine_candidates(requested: str) -> tuple[str, ...]:
    aliases = {
        "EEVEE": ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"),
        "BLENDER_EEVEE_NEXT": ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"),
        "WORKBENCH": ("BLENDER_WORKBENCH",),
    }
    return aliases.get(requested, (requested,))


def _set_render_engine(scene: Any, requested: str) -> str:
    for engine in [*_engine_candidates(requested), "CYCLES", "BLENDER_EEVEE", "BLENDER_WORKBENCH"]:
        try:
            scene.render.engine = engine
            return engine
        except TypeError:
            continue
    scene.render.engine = requested
    return requested


def _set_if_present(obj: Any, name: str, value: Any) -> None:
    if hasattr(obj, name):
        setattr(obj, name, value)


def configure_render(config: RenderConfig) -> str:
    import bpy

    scene = bpy.context.scene
    engine = _set_render_engine(scene, config.engine)
    scene.render.resolution_x = config.resolution_x
    scene.render.resolution_y = config.resolution_y
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.view_settings.view_transform = config.view_transform
    scene.view_settings.look = config.look
    scene.view_settings.exposure = config.exposure
    scene.view_settings.gamma = config.gamma

    if engine == "CYCLES" and hasattr(scene, "cycles"):
        scene.cycles.samples = config.samples
        _set_if_present(scene.cycles, "use_denoising", config.use_denoising)
        _set_if_present(scene.cycles, "use_persistent_data", config.use_persistent_data)
        if config.max_bounces is not None:
            _set_if_present(scene.cycles, "max_bounces", config.max_bounces)
        if config.transparent_max_bounces is not None:
            _set_if_present(scene.cycles, "transparent_max_bounces", config.transparent_max_bounces)
    elif engine.startswith("BLENDER_EEVEE") and hasattr(scene, "eevee"):
        _set_if_present(scene.eevee, "taa_render_samples", config.samples)
        _set_if_present(scene.eevee, "taa_samples", config.samples)
    elif engine == "BLENDER_WORKBENCH" and hasattr(scene, "display"):
        shading = getattr(scene.display, "shading", None)
        if shading:
            _set_if_present(shading, "light", "STUDIO")
            _set_if_present(shading, "color_type", "MATERIAL")
    return engine


def configure_cycles(resolution_x: int, resolution_y: int, samples: int) -> None:
    configure_render(RenderConfig(resolution_x=resolution_x, resolution_y=resolution_y, engine="CYCLES", samples=samples))


def postprocess_glow_contrast(raw: Path, finished: Path) -> bool:
    magick = shutil.which("magick")
    if not magick:
        return False
    subprocess.run(
        [
            magick,
            str(raw),
            "-colorspace",
            "sRGB",
            "(",
            "+clone",
            "-blur",
            "0x14",
            "-level",
            "72%,100%",
            ")",
            "-compose",
            "screen",
            "-composite",
            "-sigmoidal-contrast",
            "4,45%",
            "-modulate",
            "104,110,100",
            str(finished),
        ],
        check=True,
    )
    return True


def _label_font_args() -> list[str]:
    for font in [
        "/System/Library/Fonts/SFNS.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
    ]:
        if Path(font).exists():
            return ["-font", font]
    return []


def _label_point_size(tile: TileSpec) -> int:
    if tile.label_point_size is not None:
        return tile.label_point_size
    return max(8, min(13, tile.label_height - 2))


def _write_labeled_thumb(
    *,
    magick: str,
    image_path: Path,
    thumb: Path,
    label: str,
    tile: TileSpec,
) -> None:
    unlabeled_cmd = [
        magick,
        str(image_path),
        "-resize",
        f"{tile.width}x{tile.height}^",
        "-gravity",
        "center",
        "-extent",
        f"{tile.width}x{tile.height}",
        str(thumb),
    ]
    if not tile.show_labels or tile.label_height <= 0:
        subprocess.run(unlabeled_cmd, check=True)
        return

    body_height = max(1, tile.height - tile.label_height)
    label_max_chars = tile.label_max_chars or max(10, tile.width // 8)
    if len(label) > label_max_chars:
        label = f"{label[: max(1, label_max_chars - 3)]}..."
    labeled_cmd = [
        magick,
        str(image_path),
        "-resize",
        f"{tile.width}x{body_height}^",
        "-gravity",
        "center",
        "-extent",
        f"{tile.width}x{body_height}",
        "(",
        "-size",
        f"{tile.width}x{tile.label_height}",
        f"xc:{tile.background}",
        *_label_font_args(),
        "-fill",
        "#f5f0e6",
        "-gravity",
        "center",
        "-pointsize",
        str(_label_point_size(tile)),
        "-annotate",
        "+0+0",
        label,
        ")",
        "-append",
        str(thumb),
    ]
    try:
        subprocess.run(labeled_cmd, check=True)
    except subprocess.CalledProcessError:
        subprocess.run(unlabeled_cmd, check=True)


def write_contact_sheet(
    results: list[RenderResult],
    root: Path,
    out_path: Path,
    tile: TileSpec,
    reference_targets: Iterable[ReferenceTarget | Mapping[str, Any]] | None = None,
) -> None:
    magick = shutil.which("magick")
    if not magick or not results:
        return

    references = _local_reference_targets(coerce_reference_targets(reference_targets), root)
    columns = tile.columns_for_count(len(results) + len(references))
    thumbs: list[Path] = []
    for index, (target, image_path) in enumerate(references):
        thumb = out_path.parent / f"_ref_{index:03d}.thumb.png"
        label = target.caption or target.source_type or "reference"
        _write_labeled_thumb(magick=magick, image_path=image_path, thumb=thumb, label=f"ref: {label}", tile=tile)
        thumbs.append(thumb)

    for index, result in enumerate(results):
        image_path = root / (result.finished or result.raw)
        thumb = out_path.parent / f"_{index:03d}_{result.name}.thumb.png"
        label = result.label or result.name
        if tile.show_notes and result.note:
            label = f"{label} - {result.note}"
        _write_labeled_thumb(magick=magick, image_path=image_path, thumb=thumb, label=label, tile=tile)
        thumbs.append(thumb)

    rows: list[Path] = []
    for row_index in range(0, len(thumbs), columns):
        row = out_path.parent / f"_row_{row_index // columns}.png"
        row_paths = list(thumbs[row_index : row_index + columns])
        while len(row_paths) < columns:
            blank = out_path.parent / f"_blank_{row_index}_{len(row_paths)}.png"
            subprocess.run([magick, "-size", f"{tile.width}x{tile.height}", f"xc:{tile.background}", str(blank)], check=True)
            row_paths.append(blank)
            thumbs.append(blank)
        subprocess.run([magick, *[str(path) for path in row_paths], "+append", str(row)], check=True)
        rows.append(row)
    subprocess.run([magick, *[str(path) for path in rows], "-append", str(out_path)], check=True)

    for path in thumbs + rows:
        path.unlink(missing_ok=True)


def _promotion_command_for_result(template: str, result: RenderResult, index: int) -> str:
    try:
        return template.format(
            pick=result.name,
            name=result.name,
            index=index,
            label=result.label or result.name,
        )
    except KeyError as error:
        missing = error.args[0]
        raise ValueError(f"Unknown promotion command placeholder {{{missing}}}") from error


def _role_text(role: str, tags: Iterable[str] = ()) -> str:
    tag_values = normalize_variant_tags(tags)
    text = f"role `{normalize_variant_role(role)}`"
    if tag_values:
        text = f"{text}, tags `{', '.join(tag_values)}`"
    return text


def format_reference_targets_readme(targets: Iterable[ReferenceTarget | Mapping[str, Any]]) -> list[str]:
    values = coerce_reference_targets(targets)
    if not values:
        return []
    lines = ["Reference targets:", ""]
    for index, target in enumerate(values, start=1):
        cue = target.path or target.url or "(no path/url)"
        caption = f": {target.caption}" if target.caption else ""
        lines.append(f"{index}. `{cue}`{caption}")
        details = []
        if target.source_type:
            details.append(f"type `{target.source_type}`")
        if target.frame is not None:
            details.append(f"frame `{target.frame}`")
        if target.page is not None:
            details.append(f"page `{target.page}`")
        if target.crop:
            details.append(f"crop `{target.crop}`")
        if details:
            lines.append(f"   - {', '.join(details)}")
        for note in target.notes:
            lines.append(f"   - {note}")
        for match in target.match:
            lines.append(f"   - match: {match}")
    lines.extend(
        [
            "",
            "Pick the generated tile that best matches the target criteria, not merely the prettiest tile.",
        ]
    )
    return lines


def _sweep_workflow_metadata(results: list[RenderResult], promotion_command: str | None) -> dict[str, Any]:
    pick_handles = []
    for index, result in enumerate(results, start=1):
        handle = {
            "index": index,
            "name": result.name,
            "label": result.label,
            "note": result.note,
            "role": result.role,
            "tags": result.tags,
            "replicate_of": result.replicate_of,
            "replicate_index": result.replicate_index,
            "procedural_controls": result.procedural_controls,
        }
        if promotion_command:
            handle["promotion_command"] = _promotion_command_for_result(promotion_command, result, index)
        pick_handles.append(handle)

    workflow: dict[str, Any] = {
        "stage": "sweep_grid",
        "status": "needs_selected_render",
        "required_decision": "choose_the_most_promising_tile_by_visual_inspection",
        "selected_render_required_before_scene_promotion": True,
        "done_when": "selected/<pick>/selected.json exists for one chosen tile",
        "next": "inspect_contact_sheet_pick_variant_render_selected",
        "pick_handles": pick_handles,
    }
    if promotion_command:
        workflow["promotion_command_template"] = promotion_command
    return workflow


def _replicate_workflow_metadata(selected: SweepVariant, results: list[RenderResult], source_sweep: str | None) -> dict[str, Any]:
    return {
        "stage": "selected_replicate_check",
        "status": "needs_visual_review",
        "source_sweep": source_sweep,
        "selected_variant": selected.name,
        "survived_replicates": None,
        "required_decision": "compare_replicates_before_scene_promotion",
        "done_when": "replicate images are reviewed and survived_replicates is recorded",
        "replicate_handles": [
            {
                "index": index,
                "name": result.name,
                "role": result.role,
                "tags": result.tags,
                "replicate_of": result.replicate_of,
                "replicate_index": result.replicate_index,
                "procedural_controls": result.procedural_controls,
            }
            for index, result in enumerate(results, start=1)
        ],
    }


def write_readme(
    out_dir: Path,
    title: str,
    results: list[RenderResult],
    notes: list[str] | None = None,
    promotion_command: str | None = None,
    diagnostics: dict[str, Any] | None = None,
    reference_targets: Iterable[ReferenceTarget | Mapping[str, Any]] | None = None,
) -> None:
    lines = [f"# {title}", "", "Rendered variants:", ""]
    for index, result in enumerate(results, start=1):
        detail = f": {result.note}" if result.note else ""
        label = f", label `{result.label}`" if result.label and result.label != result.name else ""
        role = f", {_role_text(result.role, result.tags)}"
        procedural = _procedural_text(result.procedural_controls, result.replicate_of, result.replicate_index)
        procedural_detail = f", procedural `{procedural}`" if procedural else ""
        output = result.finished or result.raw
        output_name = Path(output).name if output else "(no image render)"
        lines.append(f"{index}. pick `{result.name}` or `{index}`{label}{role}{procedural_detail} -> `{output_name}`{detail}")
    if notes:
        lines.extend(["", "Notes:", ""])
        lines.extend(f"- {note}" for note in notes)
    if diagnostics:
        lines.extend(["", *format_diagnostics_readme(diagnostics)])
    target_lines = format_reference_targets_readme(reference_targets or ())
    if target_lines:
        lines.extend(["", *target_lines])
    lines.extend(
        [
            "",
            "Next:",
            "",
            "- Inspect `contact_sheet.png` and pick the tile that best survives thumbnail scale while moving in the desired direction.",
            "- Do not stop at the contact sheet; promote one pick into a selected render before copying settings into a scene.",
            "- Pick by exact `name` or by 1-based index from the list above.",
            "- Prefer `render_selected_from_sweep(...)` so the selected render is rebuilt from this sweep's `metadata.json`.",
            "- Use `render_selected_variant(...)` only when the script already has the same variant list in memory.",
            "- Render with a heavier config such as `RENDER_PRESETS['hero_check']`.",
            "- Done when `selected/<pick>/selected.json` exists for one chosen tile.",
        ]
    )
    if promotion_command and results:
        command = _promotion_command_for_result(promotion_command, results[0], 1)
        lines.extend(
            [
                "",
                "Promotion command template:",
                "",
                "```bash",
                command,
                "```",
                "",
                "Replace the example pick with your chosen `name` or index.",
            ]
        )
    lines.extend(
        [
            "",
            "`metadata.json` contains the full settings for each tile.",
            "",
        ]
    )
    (out_dir / "README.md").write_text("\n".join(lines))


def write_sweep_diagnostics(out_dir: Path, results: list[RenderResult], *, root: Path) -> dict[str, Any]:
    images = []
    for result in results:
        image = result.finished or result.raw
        if not image:
            continue
        path = Path(image)
        if not path.is_absolute():
            path = root / path
        images.append((result.name, path))
    diagnostics = analyze_sweep_images(images)
    for tile in diagnostics.get("tiles", []):
        if isinstance(tile, dict) and isinstance(tile.get("path"), str):
            tile["path"] = _relative_or_absolute(Path(tile["path"]), root)
    write_diagnostics(out_dir / "diagnostics.json", diagnostics)
    return diagnostics


def write_selected_readme(
    out_dir: Path,
    title: str,
    variant: SweepVariant,
    result: RenderResult,
    notes: list[str] | None = None,
    source_sweep_dir: Path | None = None,
    root: Path | None = None,
    handoff_path: str | None = None,
    reference_attempt: str | None = None,
) -> None:
    lines = [
        f"# {title}",
        "",
        f"Selected variant: `{variant.name}`",
    ]
    if variant.label and variant.label != variant.name:
        lines.append(f"Label: `{variant.label}`")
    lines.append(f"Role: `{variant.role}`")
    if variant.tags:
        lines.append(f"Tags: `{', '.join(variant.tags)}`")
    procedural = _procedural_text(_variant_procedural_controls(variant), variant.replicate_of, variant.replicate_index)
    if procedural:
        lines.append(f"Procedural controls: `{procedural}`")
    if variant.note:
        lines.append(f"Note: {variant.note}")
    if source_sweep_dir:
        root = root or Path.cwd()
        lines.append(f"Source sweep: `{_relative_or_absolute(source_sweep_dir, root)}`")
    lines.extend(["", "Rendered files:", ""])
    if result.raw:
        lines.append(f"- `{Path(result.raw).name}`")
    if not result.raw and not result.finished:
        lines.append("- No image render was requested.")
    if result.finished:
        lines.append(f"- `{Path(result.finished).name}`")
    if result.blend:
        lines.extend(
            [
                "",
                "Blender scene:",
                "",
                f"- `{Path(result.blend).name}`",
            ]
        )
        if result.open_blend_command:
            lines.extend(
                [
                    "",
                    "Open for GUI review:",
                    "",
                    "```bash",
                    result.open_blend_command,
                    "```",
                ]
            )
    if notes:
        lines.extend(["", "Notes:", ""])
        lines.extend(f"- {note}" for note in notes)
    if handoff_path:
        lines.extend(["", "Handoff:", "", f"- `{handoff_path}` records the prompt card for the next artist or agent."])
    if reference_attempt:
        lines.extend(["", "Reference comparison:", "", f"- `{reference_attempt}` pairs the target reference with this attempt."])
    lines.extend(["", "`selected.json` contains the chosen settings, render config, and provenance.", ""])
    (out_dir / "README.md").write_text("\n".join(lines))


def write_reference_attempt_pair(
    out_dir: Path,
    result: RenderResult,
    *,
    reference_targets: Iterable[ReferenceTarget | Mapping[str, Any]] | None = None,
    root: Path,
) -> str | None:
    local_targets = _local_reference_targets(coerce_reference_targets(reference_targets), root)
    image = result.finished or result.raw
    if not local_targets or not image:
        return None
    magick = shutil.which("magick")
    if not magick:
        return None
    reference, reference_path = local_targets[0]
    attempt_path = Path(image)
    if not attempt_path.is_absolute():
        attempt_path = root / attempt_path
    out_path = out_dir / "reference_attempt.png"
    label = reference.caption or "reference"
    subprocess.run(
        [
            magick,
            "(",
            str(reference_path),
            "-resize",
            "640x640^",
            "-gravity",
            "center",
            "-extent",
            "640x640",
            "-pointsize",
            "24",
            "-annotate",
            "+24+40",
            f"reference: {label}",
            ")",
            "(",
            str(attempt_path),
            "-resize",
            "640x640^",
            "-gravity",
            "center",
            "-extent",
            "640x640",
            "-pointsize",
            "24",
            "-annotate",
            "+24+40",
            f"attempt: {result.name}",
            ")",
            "+append",
            str(out_path),
        ],
        check=True,
    )
    return _relative_or_absolute(out_path, root)


def _source_sweep_fingerprint(source_sweep_dir: Path | None) -> dict[str, Any] | None:
    if source_sweep_dir is None:
        return None
    metadata_path = Path(source_sweep_dir) / "metadata.json"
    if not metadata_path.exists():
        return None
    try:
        payload = json.loads(metadata_path.read_text())
    except json.JSONDecodeError:
        return None
    fingerprint = payload.get("fingerprint")
    return fingerprint if isinstance(fingerprint, dict) else None


def write_replicate_readme(
    out_dir: Path,
    title: str,
    selected: SweepVariant,
    results: list[RenderResult],
    notes: list[str] | None = None,
    source_sweep_dir: Path | None = None,
    root: Path | None = None,
) -> None:
    lines = [
        f"# {title}",
        "",
        f"Replicate check for selected variant: `{selected.name}`",
        "Survived replicate checks: `unknown` until the replicate strip is visually reviewed.",
        "",
        "Do not promote a texture/noise-heavy tile solely because one procedural sample looked good.",
    ]
    if source_sweep_dir:
        root = root or Path.cwd()
        lines.append(f"Source sweep: `{_relative_or_absolute(source_sweep_dir, root)}`")
    lines.extend(["", "Rendered replicates:", ""])
    for index, result in enumerate(results, start=1):
        procedural = _procedural_text(result.procedural_controls, result.replicate_of, result.replicate_index)
        procedural_detail = f", procedural `{procedural}`" if procedural else ""
        output = result.finished or result.raw
        output_name = Path(output).name if output else "(no image render)"
        lines.append(f"{index}. `{result.name}`{procedural_detail} -> `{output_name}`")
    if notes:
        lines.extend(["", "Notes:", ""])
        lines.extend(f"- {note}" for note in notes)
    lines.extend(
        [
            "",
            "Next:",
            "",
            "- Inspect `replicates.png` and full-size raw/finished files.",
            "- Mark the winner as survived only if the core visual read holds across the seed/phase changes.",
            "- If one replicate collapses, rerun the broader sweep with more stable settings before promotion.",
            "",
            "`replicates.json` contains the picked settings, procedural controls, render config, and review status.",
            "",
        ]
    )
    (out_dir / "README.md").write_text("\n".join(lines))


def _render_variant(
    *,
    variant: SweepVariant,
    build_scene: Callable[[Any], None],
    out_dir: Path,
    root: Path,
    config: RenderConfig,
    postprocess: Callable[[Path, Path], bool] | None,
    file_suffix: str = "",
    render_label: str = "sweep",
    save_blend_path: Path | None = None,
    render_image: bool = True,
) -> RenderResult:
    suffix = f".{file_suffix}" if file_suffix else ""
    raw = out_dir / f"{variant.name}{suffix}.raw.png"
    finished = out_dir / f"{variant.name}{suffix}.finished.png"
    expected_fingerprint = render_cache_fingerprint(
        root=root,
        variant_name=variant.name,
        variant_settings=settings_to_jsonable(variant.settings),
        render_config=settings_to_jsonable(config),
        build_scene=build_scene,
        postprocess=postprocess,
        extra={"render_label": render_label, "file_suffix": file_suffix},
    )
    wrote_finished = finished.exists()
    cache_warning = None
    if config.reuse_existing and raw.exists() and not save_blend_path and render_image:
        cache_status = fingerprint_status(raw, expected_fingerprint["fingerprint"])
        if fingerprint_matches(raw, expected_fingerprint):
            postprocess_started = time.perf_counter()
            ran_postprocess = False
            if not wrote_finished and postprocess:
                ran_postprocess = True
                wrote_finished = postprocess(raw, finished)
            postprocess_seconds = time.perf_counter() - postprocess_started if ran_postprocess else 0.0
            print(f"Reusing fresh {render_label} variant {variant.name}")
            return RenderResult(
                name=variant.name,
                raw=_relative_or_absolute(raw, root),
                finished=_relative_or_absolute(finished, root) if wrote_finished else None,
                settings=settings_to_jsonable(variant.settings),
                label=variant.label,
                note=variant.note,
                role=variant.role,
                tags=variant.tags,
                replicate_of=variant.replicate_of,
                replicate_index=variant.replicate_index,
                procedural_controls=_variant_procedural_controls(variant),
                postprocess_seconds=postprocess_seconds,
                skipped_existing=True,
                cache_status=cache_status,
                fingerprint=expected_fingerprint,
            )
        cache_warning = f"existing cache was {cache_status}; rerendered instead of reusing"
        print(f"Existing {render_label} variant {variant.name} is {cache_status}; rerendering")

    import bpy

    build_started = time.perf_counter()
    build_scene(variant.settings)
    build_seconds = time.perf_counter() - build_started
    engine = configure_render(config)
    if config.camera_name:
        bpy.context.scene.camera = bpy.data.objects[config.camera_name]

    blend_value = None
    open_blend_command = None
    if save_blend_path:
        save_blend_path.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(save_blend_path))
        blend_value = _relative_or_absolute(save_blend_path, root)
        open_blend_command = _open_blend_command(save_blend_path, root)

    if not render_image:
        print(f"Exported {render_label} variant {variant.name} scene without rendering")
        return RenderResult(
            name=variant.name,
            raw=None,
            finished=None,
            settings=settings_to_jsonable(variant.settings),
            label=variant.label,
            note=variant.note,
            role=variant.role,
            tags=variant.tags,
            replicate_of=variant.replicate_of,
            replicate_index=variant.replicate_index,
            procedural_controls=_variant_procedural_controls(variant),
            blend=blend_value,
            open_blend_command=open_blend_command,
            render_skipped=True,
            engine=engine,
            camera_name=config.camera_name,
            build_seconds=build_seconds,
            render_seconds=0.0,
            postprocess_seconds=0.0,
            cache_status="scene_export",
            fingerprint=expected_fingerprint,
        )

    bpy.context.scene.render.filepath = str(raw)
    print(f"Rendering {render_label} variant {variant.name} ({engine}, {config.samples} samples)")
    render_started = time.perf_counter()
    bpy.ops.render.render(write_still=True)
    render_seconds = time.perf_counter() - render_started
    postprocess_started = time.perf_counter()
    wrote_finished = postprocess(raw, finished) if postprocess else False
    postprocess_seconds = time.perf_counter() - postprocess_started
    write_fingerprint_record(raw.with_suffix(".fingerprint.json"), expected_fingerprint)
    return RenderResult(
        name=variant.name,
        raw=_relative_or_absolute(raw, root),
        finished=_relative_or_absolute(finished, root) if wrote_finished else None,
        settings=settings_to_jsonable(variant.settings),
        label=variant.label,
        note=variant.note,
        role=variant.role,
        tags=variant.tags,
        replicate_of=variant.replicate_of,
        replicate_index=variant.replicate_index,
        procedural_controls=_variant_procedural_controls(variant),
        blend=blend_value,
        open_blend_command=open_blend_command,
        engine=engine,
        camera_name=config.camera_name,
        build_seconds=build_seconds,
        render_seconds=render_seconds,
        postprocess_seconds=postprocess_seconds,
        cache_status="rendered",
        cache_warning=cache_warning,
        fingerprint=expected_fingerprint,
    )


def render_sweep(
    *,
    variants: Iterable[SweepVariant],
    build_scene: Callable[[Any], None],
    out_dir: Path,
    root: Path | None = None,
    config: RenderConfig | None = None,
    postprocess: Callable[[Path, Path], bool] | None = postprocess_glow_contrast,
    title: str = "Blender Sweep",
    notes: list[str] | None = None,
    promotion_command: str | None = None,
    reference_targets: Iterable[ReferenceTarget | Mapping[str, Any]] | None = None,
    square: bool = False,
) -> list[RenderResult]:
    """Render a sequence of variants from one scene-builder function.

    `build_scene(settings)` should fully rebuild the Blender scene for a variant.
    This function renders each variant, writes raw/finished PNGs, metadata,
    README, and `contact_sheet.png`.
    """
    variant_list = list(variants)
    cfg = config or RenderConfig()
    if square:
        cfg = dataclasses.replace(cfg, tile=cfg.tile.with_auto_columns())
    root = root or Path.cwd()
    out_dir.mkdir(parents=True, exist_ok=True)
    target_list = coerce_reference_targets(reference_targets)

    results: list[RenderResult] = []
    sweep_started = time.perf_counter()
    for variant in variant_list:
        results.append(
            _render_variant(
                variant=variant,
                build_scene=build_scene,
                out_dir=out_dir,
                root=root,
                config=cfg,
                postprocess=postprocess,
            )
        )

    write_contact_sheet(results, root, out_dir / "contact_sheet.png", cfg.tile, reference_targets=target_list)
    diagnostics = write_sweep_diagnostics(out_dir, results, root=root)
    write_readme(
        out_dir,
        title,
        results,
        notes,
        promotion_command=promotion_command,
        diagnostics=diagnostics,
        reference_targets=target_list,
    )
    sweep_fingerprint = make_artifact_fingerprint(
        "sweep_metadata",
        {
            "render_config": settings_to_jsonable(cfg),
            "variants": [
                {
                    "name": result.name,
                    "settings": result.settings,
                    "fingerprint": result.fingerprint.get("fingerprint") if result.fingerprint else None,
                }
                for result in results
            ],
        },
    )
    (out_dir / "metadata.json").write_text(
        json.dumps(
            {
                "fingerprint": sweep_fingerprint,
                "title": title,
                "render_config": settings_to_jsonable(cfg),
                "contact_sheet": {
                    "columns": cfg.tile.columns_for_count(len(results) + len(_local_reference_targets(target_list, root))),
                    "tile": settings_to_jsonable(cfg.tile),
                    "reference_panels": len(_local_reference_targets(target_list, root)),
                },
                "reference_targets": reference_targets_to_metadata(target_list),
                "workflow": _sweep_workflow_metadata(results, promotion_command),
                "diagnostics": diagnostics,
                "total_seconds": time.perf_counter() - sweep_started,
                "variants": [dataclasses.asdict(result) for result in results],
            },
            indent=2,
        )
    )
    write_review_page(out_dir, root=root)
    return results


def render_selected_variant(
    *,
    variants: Iterable[SweepVariant],
    pick: str | int,
    build_scene: Callable[[Any], None],
    out_dir: Path,
    root: Path | None = None,
    config: RenderConfig | None = None,
    postprocess: Callable[[Path, Path], bool] | None = postprocess_glow_contrast,
    title: str = "Selected Blender Render",
    notes: list[str] | None = None,
    handoff_notes: Mapping[str, Any] | None = None,
    reference_targets: Iterable[ReferenceTarget | Mapping[str, Any]] | None = None,
    source_sweep_dir: Path | None = None,
    save_blend: bool = False,
    render_image: bool = True,
    allow_anchor_promotion: bool = False,
) -> RenderResult:
    """Render one picked variant at higher quality after inspecting a grid."""
    variant_list = list(variants)
    selected = select_variant(variant_list, pick)
    if selected.role in PROTECTED_PROMOTION_ROLES and not allow_anchor_promotion:
        raise ValueError(
            f"Refusing to promote {selected.name!r} with role {selected.role!r}; "
            "pass allow_anchor_promotion=True after confirming this is intentional"
        )
    cfg = config or RenderConfig.hero_check()
    root = root or Path.cwd()
    out_dir.mkdir(parents=True, exist_ok=True)
    if not render_image and not save_blend:
        raise ValueError("render_image=False requires save_blend=True so the selected pass writes an artifact")

    selected_started = time.perf_counter()
    blend_path = out_dir / f"{_safe_output_name(selected.name)}.blend" if save_blend else None
    result = _render_variant(
        variant=selected,
        build_scene=build_scene,
        out_dir=out_dir,
        root=root,
        config=cfg,
        postprocess=postprocess,
        file_suffix="hero",
        render_label="selected",
        save_blend_path=blend_path,
        render_image=render_image,
    )
    source_value = _relative_or_absolute(source_sweep_dir, root) if source_sweep_dir else None
    source_fingerprint = _source_sweep_fingerprint(source_sweep_dir)
    selected_fingerprint = make_artifact_fingerprint(
        "selected_render",
        {
            "pick": pick,
            "source_sweep": source_value,
            "source_sweep_fingerprint": source_fingerprint.get("fingerprint") if source_fingerprint else None,
            "render_config": settings_to_jsonable(cfg),
            "result_fingerprint": result.fingerprint.get("fingerprint") if result.fingerprint else None,
        },
    )
    payload = {
        "fingerprint": selected_fingerprint,
        "pick": pick,
        "source_sweep": source_value,
        "source_sweep_fingerprint": source_fingerprint,
        "selected": {
            "name": selected.name,
            "label": selected.label,
            "note": selected.note,
            "role": selected.role,
            "tags": selected.tags,
            "replicate_of": selected.replicate_of,
            "replicate_index": selected.replicate_index,
            "procedural_controls": _variant_procedural_controls(selected),
            "settings": settings_to_jsonable(selected.settings),
        },
        "render_config": settings_to_jsonable(cfg),
        "workflow": {
            "stage": "selected_render",
            "status": "complete",
            "source_sweep": source_value,
            "satisfies": "selected_render_required_before_scene_promotion",
        },
        "total_seconds": time.perf_counter() - selected_started,
        "result": dataclasses.asdict(result),
    }
    if result.blend:
        payload["blend_export"] = {
            "path": result.blend,
            "open_command": result.open_blend_command,
            "camera_name": cfg.camera_name,
            "render_profile": settings_to_jsonable(cfg),
            "render_image": render_image,
            "source_sweep": source_value,
        }
    target_list = coerce_reference_targets(reference_targets)
    reference_attempt = write_reference_attempt_pair(out_dir, result, reference_targets=target_list, root=root)
    if target_list:
        payload["reference_targets"] = reference_targets_to_metadata(target_list)
    if reference_attempt:
        payload["reference_attempt"] = {
            "path": reference_attempt,
            "source": payload.get("reference_targets", [None])[0],
        }
    payload["handoff"] = write_handoff_card(
        out_dir=out_dir,
        selected_payload=payload,
        root=root,
        title=f"{title} Handoff",
        handoff_notes=handoff_notes,
        source_sweep_dir=source_sweep_dir,
    )
    write_selected_readme(
        out_dir,
        title,
        selected,
        result,
        notes=notes,
        source_sweep_dir=source_sweep_dir,
        root=root,
        handoff_path="handoff.md",
        reference_attempt=Path(reference_attempt).name if reference_attempt else None,
    )
    (out_dir / "selected.json").write_text(
        json.dumps(
            payload,
            indent=2,
        )
    )
    return result


def render_selected_from_sweep(
    *,
    sweep_dir: Path,
    pick: str | int | None = None,
    build_scene: Callable[[Any], None],
    out_dir: Path | None = None,
    root: Path | None = None,
    config: RenderConfig | None = None,
    postprocess: Callable[[Path, Path], bool] | None = postprocess_glow_contrast,
    title: str = "Selected Blender Render",
    notes: list[str] | None = None,
    handoff_notes: Mapping[str, Any] | None = None,
    reference_targets: Iterable[ReferenceTarget | Mapping[str, Any]] | None = None,
    source_sweep_dir: Path | None = None,
    save_blend: bool = False,
    render_image: bool = True,
    allow_anchor_promotion: bool = False,
) -> RenderResult:
    """Promote one tile from a prior sweep grid into a heavier selected render."""
    sweep_dir = Path(sweep_dir)
    if pick is None:
        from .review_log import selected_pick_from_review

        pick = selected_pick_from_review(sweep_dir)
        if pick is None:
            raise ValueError(f"No pick provided and {sweep_dir / 'review.json'} has no promotable winner")
    variant_list = variants_from_sweep_metadata(sweep_dir)
    if reference_targets is None:
        try:
            source_payload = json.loads((sweep_dir / "metadata.json").read_text())
            raw_targets = source_payload.get("reference_targets")
            reference_targets = raw_targets if isinstance(raw_targets, list) else None
        except (OSError, json.JSONDecodeError):
            reference_targets = None
    selected = select_variant(variant_list, pick)
    target_out_dir = out_dir or sweep_dir / "selected" / _safe_output_name(selected.name)
    return render_selected_variant(
        variants=variant_list,
        pick=pick,
        build_scene=build_scene,
        out_dir=target_out_dir,
        root=root,
        config=config,
        postprocess=postprocess,
        title=title,
        notes=notes,
        handoff_notes=handoff_notes,
        reference_targets=reference_targets,
        source_sweep_dir=source_sweep_dir or sweep_dir,
        save_blend=save_blend,
        render_image=render_image,
        allow_anchor_promotion=allow_anchor_promotion,
    )


def render_selected_replicates(
    *,
    variants: Iterable[SweepVariant],
    pick: str | int,
    build_scene: Callable[[Any], None],
    out_dir: Path,
    root: Path | None = None,
    config: RenderConfig | None = None,
    postprocess: Callable[[Path, Path], bool] | None = postprocess_glow_contrast,
    title: str = "Selected Procedural Replicates",
    notes: list[str] | None = None,
    source_sweep_dir: Path | None = None,
    seeds: Iterable[int] = (0, 1, 2),
    phases: Iterable[float] | None = None,
    seed_field: str = "variation_seed",
    phase_field: str = "noise_phase",
    save_blend: bool = False,
    render_image: bool = True,
    allow_anchor_promotion: bool = False,
) -> list[RenderResult]:
    """Render one selected variant across procedural seeds/phases."""
    variant_list = list(variants)
    selected = select_variant(variant_list, pick)
    if selected.role in PROTECTED_PROMOTION_ROLES and not allow_anchor_promotion:
        raise ValueError(
            f"Refusing to replicate {selected.name!r} with role {selected.role!r}; "
            "pass allow_anchor_promotion=True after confirming this is intentional"
        )
    replicate_list = replicate_variants(
        selected,
        seeds=seeds,
        phases=phases,
        seed_field=seed_field,
        phase_field=phase_field,
    )
    cfg = config or dataclasses.replace(RenderConfig.hero_check(), tile=TileSpec.filmstrip(columns=min(6, len(replicate_list))))
    root = root or Path.cwd()
    out_dir.mkdir(parents=True, exist_ok=True)
    if not render_image and not save_blend:
        raise ValueError("render_image=False requires save_blend=True so the replicate pass writes an artifact")

    replicate_started = time.perf_counter()
    results: list[RenderResult] = []
    for variant in replicate_list:
        blend_path = out_dir / f"{_safe_output_name(variant.name)}.blend" if save_blend else None
        results.append(
            _render_variant(
                variant=variant,
                build_scene=build_scene,
                out_dir=out_dir,
                root=root,
                config=cfg,
                postprocess=postprocess,
                file_suffix="replicate",
                render_label="selected replicate",
                save_blend_path=blend_path,
                render_image=render_image,
            )
        )

    if any(result.finished or result.raw for result in results):
        write_contact_sheet(results, root, out_dir / "replicates.png", cfg.tile)
    write_replicate_readme(out_dir, title, selected, results, notes=notes, source_sweep_dir=source_sweep_dir, root=root)
    source_value = _relative_or_absolute(source_sweep_dir, root) if source_sweep_dir else None
    payload = {
        "pick": pick,
        "source_sweep": source_value,
        "selected": {
            "name": selected.name,
            "label": selected.label,
            "note": selected.note,
            "role": selected.role,
            "tags": selected.tags,
            "replicate_of": selected.replicate_of,
            "replicate_index": selected.replicate_index,
            "procedural_controls": _variant_procedural_controls(selected),
            "settings": settings_to_jsonable(selected.settings),
        },
        "render_config": settings_to_jsonable(cfg),
        "workflow": _replicate_workflow_metadata(selected, results, source_value),
        "total_seconds": time.perf_counter() - replicate_started,
        "replicates": [dataclasses.asdict(result) for result in results],
    }
    (out_dir / "replicates.json").write_text(json.dumps(payload, indent=2))
    return results


def render_selected_replicates_from_sweep(
    *,
    sweep_dir: Path,
    pick: str | int,
    build_scene: Callable[[Any], None],
    out_dir: Path | None = None,
    root: Path | None = None,
    config: RenderConfig | None = None,
    postprocess: Callable[[Path, Path], bool] | None = postprocess_glow_contrast,
    title: str = "Selected Procedural Replicates",
    notes: list[str] | None = None,
    source_sweep_dir: Path | None = None,
    seeds: Iterable[int] = (0, 1, 2),
    phases: Iterable[float] | None = None,
    seed_field: str = "variation_seed",
    phase_field: str = "noise_phase",
    save_blend: bool = False,
    render_image: bool = True,
    allow_anchor_promotion: bool = False,
) -> list[RenderResult]:
    """Render seed/phase replicates for one picked tile from prior metadata."""
    sweep_dir = Path(sweep_dir)
    variant_list = variants_from_sweep_metadata(sweep_dir)
    selected = select_variant(variant_list, pick)
    target_out_dir = out_dir or sweep_dir / "selected" / _safe_output_name(selected.name) / "replicates"
    return render_selected_replicates(
        variants=variant_list,
        pick=pick,
        build_scene=build_scene,
        out_dir=target_out_dir,
        root=root,
        config=config,
        postprocess=postprocess,
        title=title,
        notes=notes,
        source_sweep_dir=source_sweep_dir or sweep_dir,
        seeds=seeds,
        phases=phases,
        seed_field=seed_field,
        phase_field=phase_field,
        save_blend=save_blend,
        render_image=render_image,
        allow_anchor_promotion=allow_anchor_promotion,
    )
