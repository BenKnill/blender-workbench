from __future__ import annotations

import dataclasses
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from blender_workbench.camera import add_orbit_camera, camera_distance_for_matching_framing, look_at
from blender_workbench.materials import emission_material, principled_material
from blender_workbench.sweep import SweepVariant


DEPTH_OF_FIELD_CAMERA = "depth_of_field_camera"
FOCUS_PLANES = ("foreground", "subject", "background")


def _matched(lens: float) -> float:
    return camera_distance_for_matching_framing(lens, base_lens_mm=70.0, base_distance=4.8)


@dataclass(frozen=True)
class DepthOfFieldSettings:
    focus_plane: str = "subject"
    aperture_fstop: float = 3.2
    camera_lens: float = 70.0
    camera_distance: float = _matched(70.0)
    foreground_occluder_distance: float = 1.0
    foreground_occluder_scale: float = 1.0
    background_marker_density: int = 8
    background_marker_contrast: float = 0.62
    bokeh_highlight_size: float = 0.07
    bokeh_highlight_strength: float = 0.90
    subject_edge_ruler: bool = True


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _normalized_focus_plane(value: str) -> str:
    if value in FOCUS_PLANES:
        return value
    return "subject"


def _distance(a: Any, b: tuple[float, float, float]) -> float:
    return math.sqrt((float(a.x) - b[0]) ** 2 + (float(a.y) - b[1]) ** 2 + (float(a.z) - b[2]) ** 2)


def coerce_depth_of_field_settings(settings: DepthOfFieldSettings | Mapping[str, Any] | None = None) -> DepthOfFieldSettings:
    if isinstance(settings, DepthOfFieldSettings):
        return settings
    data = dataclasses.asdict(DepthOfFieldSettings())
    if settings:
        data.update({key: value for key, value in dict(settings).items() if key in data})
    data["focus_plane"] = _normalized_focus_plane(str(data["focus_plane"]))
    return DepthOfFieldSettings(**data)


def focus_plane_targets(settings: DepthOfFieldSettings | Mapping[str, Any] | None = None) -> dict[str, tuple[float, float, float]]:
    dof = coerce_depth_of_field_settings(settings)
    foreground_y = -0.86 * _clamp(dof.foreground_occluder_distance, 0.45, 1.65)
    return {
        "foreground": (0.0, foreground_y, 0.74),
        "subject": (0.0, 0.32, 0.82),
        "background": (0.0, 2.28, 0.92),
    }


def depth_of_field_descriptor(settings: DepthOfFieldSettings | Mapping[str, Any] | None = None) -> dict[str, Any]:
    dof = coerce_depth_of_field_settings(settings)
    return {
        "technique": "camera_depth_of_field",
        "available_focus_planes": FOCUS_PLANES,
        "focus_plane": dof.focus_plane,
        "aperture_fstop": max(0.1, float(dof.aperture_fstop)),
        "camera_lens": max(1.0, float(dof.camera_lens)),
        "matched_framing_distance": float(dof.camera_distance),
        "foreground_occluder_distance": _clamp(dof.foreground_occluder_distance, 0.45, 1.65),
        "foreground_occluder_scale": _clamp(dof.foreground_occluder_scale, 0.35, 2.1),
        "background_marker_density": max(1, int(dof.background_marker_density)),
        "background_marker_contrast": _clamp(dof.background_marker_contrast, 0.0, 1.0),
        "diagnostics": ("foreground_slats", "main_subject", "background_markers", "bokeh_highlights"),
    }


def _variant_settings(overrides: Mapping[str, Any]) -> dict[str, Any]:
    data = dataclasses.asdict(DepthOfFieldSettings())
    data.update(dict(overrides))
    dof = coerce_depth_of_field_settings(data)
    payload = dataclasses.asdict(dof)
    payload["focus_diagnostics"] = depth_of_field_descriptor(dof)
    payload["focus_targets"] = focus_plane_targets(dof)
    return payload


def depth_of_field_variants(*, prefix: str = "dof") -> list[SweepVariant]:
    cases: tuple[tuple[str, Mapping[str, Any]], ...] = (
        ("subject_moderate", {"focus_plane": "subject", "aperture_fstop": 4.0}),
        ("subject_shallow", {"focus_plane": "subject", "aperture_fstop": 2.0, "bokeh_highlight_strength": 1.05}),
        ("foreground_focus", {"focus_plane": "foreground", "aperture_fstop": 2.4, "foreground_occluder_scale": 1.18}),
        ("background_focus", {"focus_plane": "background", "aperture_fstop": 2.8, "background_marker_contrast": 0.78}),
        ("tele_bokeh", {"focus_plane": "subject", "camera_lens": 105.0, "camera_distance": _matched(105.0), "aperture_fstop": 2.2, "bokeh_highlight_size": 0.10}),
        ("wide_context", {"focus_plane": "subject", "camera_lens": 45.0, "camera_distance": _matched(45.0), "aperture_fstop": 2.8}),
        ("close_occluders", {"focus_plane": "subject", "foreground_occluder_distance": 0.62, "foreground_occluder_scale": 1.46, "aperture_fstop": 2.6}),
        ("busy_background", {"focus_plane": "subject", "background_marker_density": 14, "background_marker_contrast": 0.86, "bokeh_highlight_strength": 1.22}),
        ("all_sharp_fail", {"focus_plane": "subject", "aperture_fstop": 22.0, "bokeh_highlight_strength": 0.35}),
        ("wrong_plane_fail", {"focus_plane": "foreground", "aperture_fstop": 1.6, "foreground_occluder_scale": 1.42}),
        ("over_blurred_fail", {"focus_plane": "subject", "camera_lens": 118.0, "camera_distance": _matched(118.0), "aperture_fstop": 0.7, "bokeh_highlight_size": 0.16}),
    )
    roles = {
        "subject_moderate": "baseline",
        "all_sharp_fail": "failure_anchor",
        "wrong_plane_fail": "failure_anchor",
        "over_blurred_fail": "failure_anchor",
    }
    tags_by_label = {
        "all_sharp_fail": ("all_sharp",),
        "wrong_plane_fail": ("wrong_focus_plane",),
        "over_blurred_fail": ("over_blurred", "too_far"),
    }
    variants: list[SweepVariant] = []
    for label, overrides in cases:
        name = f"{prefix}_{label}" if prefix else label
        variants.append(
            SweepVariant(
                name=name,
                label=label,
                settings=_variant_settings(overrides),
                note="depth-of-field scout: focus plane, aperture, lens, occluders, and bokeh highlights",
                role=roles.get(label, "candidate"),
                tags=("depth_of_field", "focal_blur", *tags_by_label.get(label, ())),
            )
        )
    return variants


def clear_scene() -> None:
    import bpy

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def _shade_smooth() -> None:
    import bpy

    try:
        bpy.ops.object.shade_smooth()
    except RuntimeError:
        pass


def _cube(name: str, location, scale, mat: Any, rotation=(0.0, 0.0, 0.0)) -> Any:
    import bpy

    bpy.ops.mesh.primitive_cube_add(size=1, location=location, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(mat)
    return obj


def _configure_world() -> None:
    import bpy

    world = bpy.context.scene.world or bpy.data.worlds.new("depth of field world")
    bpy.context.scene.world = world
    world.color = (0.018, 0.019, 0.024)


def _add_floor_and_wall(settings: DepthOfFieldSettings) -> None:
    import bpy

    floor_mat = principled_material("dof matte floor", (0.20, 0.205, 0.22, 1.0), roughness=0.86)
    wall_mat = principled_material("dof marker wall", (0.105, 0.115, 0.145, 1.0), roughness=0.9)
    stripe_mat = principled_material("dof dark floor stripes", (0.035, 0.038, 0.048, 1.0), roughness=0.92)

    bpy.ops.mesh.primitive_plane_add(size=6.8, location=(0.0, 0.55, 0.0))
    floor = bpy.context.object
    floor.name = "depth of field floor"
    floor.data.materials.append(floor_mat)

    bpy.ops.mesh.primitive_plane_add(size=5.8, location=(0.0, 2.48, 1.32), rotation=(math.pi / 2, 0.0, 0.0))
    wall = bpy.context.object
    wall.name = "background focus marker wall"
    wall.scale.z = 0.62
    wall.data.materials.append(wall_mat)

    for index, y in enumerate((-1.1, -0.55, 0.0, 0.55, 1.1, 1.65, 2.2)):
        width = 3.2 - index * 0.24
        _cube(f"floor focus distance stripe {index}", (0.0, y, 0.014), (width, 0.018, 0.012), stripe_mat)

    contrast = _clamp(settings.background_marker_contrast, 0.0, 1.0)
    density = max(3, min(18, int(settings.background_marker_density)))
    for index in range(density):
        frac = index / max(1, density - 1)
        x = -2.18 + frac * 4.36
        height = 0.24 + 0.18 * ((index % 4) / 3)
        shade = 0.18 + contrast * (0.16 + 0.52 * ((index % 5) / 4))
        marker_mat = principled_material(f"background blur marker {index}", (shade, shade * 0.95, shade * 0.78, 1.0), roughness=0.74)
        _cube(f"background vertical marker {index:02d}", (x, 2.34, 0.34 + height), (0.055, 0.055, height), marker_mat)

    glow_mat = emission_material("small bokeh highlight dots", (1.0, 0.78, 0.46, 1.0), settings.bokeh_highlight_strength)
    for index, (x, z) in enumerate(((-1.72, 1.62), (-0.86, 1.42), (-0.15, 1.74), (0.74, 1.34), (1.52, 1.58))):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8, radius=settings.bokeh_highlight_size, location=(x, 2.30, z))
        dot = bpy.context.object
        dot.name = f"background bokeh dot {index}"
        dot.scale.y = 0.24
        dot.data.materials.append(glow_mat)
        _shade_smooth()


def _add_foreground_slats(settings: DepthOfFieldSettings) -> None:
    dark = principled_material("foreground slat dark lacquer", (0.025, 0.024, 0.026, 1.0), roughness=0.58)
    blue = principled_material("foreground slat cool edge", (0.16, 0.26, 0.44, 1.0), roughness=0.62)
    y = -0.86 * _clamp(settings.foreground_occluder_distance, 0.45, 1.65)
    scale = _clamp(settings.foreground_occluder_scale, 0.35, 2.1)
    for index, x in enumerate((-1.55, -0.94, 0.94, 1.55)):
        height = (0.58 + 0.16 * (index % 2)) * scale
        mat = blue if index % 2 else dark
        _cube(f"foreground focus slat {index}", (x, y - index * 0.025, 0.30 + height * 0.5), (0.045 * scale, 0.045, height), mat)


def _add_subject(settings: DepthOfFieldSettings) -> None:
    import bpy

    subject = principled_material("sharpness test subject warm ceramic", (0.74, 0.58, 0.38, 1.0), roughness=0.56)
    edge = principled_material("subject sharp edge ruler", (0.045, 0.040, 0.035, 1.0), roughness=0.7)
    highlight = principled_material("subject small glossy cap", (0.82, 0.78, 0.68, 1.0), roughness=0.28)

    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=0.55, location=(0.0, 0.32, 0.76))
    body = bpy.context.object
    body.name = "main subject focus body"
    body.scale = (0.78, 0.62, 1.05)
    body.data.materials.append(subject)
    _shade_smooth()

    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=12, radius=0.18, location=(-0.19, 0.03, 1.05))
    cap = bpy.context.object
    cap.name = "subject highlight cap"
    cap.scale = (1.15, 0.58, 0.45)
    cap.data.materials.append(highlight)
    _shade_smooth()

    if settings.subject_edge_ruler:
        for index, z in enumerate((0.36, 0.58, 0.80, 1.02)):
            _cube(f"subject edge ruler tick {index}", (0.56, 0.14, z), (0.12, 0.018, 0.018), edge)
        _cube("subject vertical sharpness ruler", (0.56, 0.14, 0.70), (0.018, 0.018, 0.46), edge)


def _add_focus_plane_ticks(settings: DepthOfFieldSettings) -> None:
    mats = {
        "foreground": emission_material("foreground focus tick", (0.46, 0.68, 1.0, 1.0), 0.22),
        "subject": emission_material("subject focus tick", (1.0, 0.82, 0.42, 1.0), 0.22),
        "background": emission_material("background focus tick", (0.72, 1.0, 0.72, 1.0), 0.22),
    }
    for plane, target in focus_plane_targets(settings).items():
        _cube(f"{plane} named focus plane tick", (target[0] - 0.34, target[1], target[2]), (0.16, 0.02, 0.02), mats[plane])


def _add_lights() -> None:
    import bpy

    bpy.ops.object.light_add(type="AREA", location=(-2.8, -2.1, 2.6))
    key = bpy.context.object
    key.name = "soft product key"
    key.data.energy = 420
    key.data.size = 4.2
    look_at(key, (0.0, 0.38, 0.75))

    bpy.ops.object.light_add(type="POINT", location=(1.8, 2.0, 1.7))
    rim = bpy.context.object
    rim.name = "small bokeh rim"
    rim.data.energy = 82
    rim.data.color = (1.0, 0.78, 0.54)


def _add_camera(settings: DepthOfFieldSettings) -> None:
    import bpy

    camera = add_orbit_camera(
        name=DEPTH_OF_FIELD_CAMERA,
        target=(0.0, 0.35, 0.82),
        distance=settings.camera_distance,
        lens_mm=settings.camera_lens,
        yaw_degrees=0.0,
        pitch_degrees=6.0,
    )
    focus_target = focus_plane_targets(settings)[settings.focus_plane]
    camera.data.dof.use_dof = True
    camera.data.dof.aperture_fstop = max(0.1, settings.aperture_fstop)
    camera.data.dof.focus_distance = _distance(camera.location, focus_target)
    camera.data.dof.aperture_blades = 7
    camera.data.dof.aperture_ratio = 1.0
    bpy.context.scene.camera = camera


def build_depth_of_field_scene(settings: DepthOfFieldSettings | Mapping[str, Any] | None = None) -> None:
    dof_settings = coerce_depth_of_field_settings(settings)
    clear_scene()
    _configure_world()
    _add_floor_and_wall(dof_settings)
    _add_foreground_slats(dof_settings)
    _add_subject(dof_settings)
    _add_focus_plane_ticks(dof_settings)
    _add_lights()
    _add_camera(dof_settings)
