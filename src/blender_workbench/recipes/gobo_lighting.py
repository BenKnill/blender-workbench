from __future__ import annotations

import dataclasses
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from blender_workbench.materials import principled_material
from blender_workbench.sweep import SweepVariant, named_variants


GOBO_CAMERA = "gobo_camera"


@dataclass(frozen=True)
class GoboLightingSettings:
    pattern: str = "window"
    blocker_count: int = 5
    blocker_width: float = 0.10
    blocker_gap: float = 0.34
    blocker_distance: float = -0.65
    blocker_rotation: float = 0.0
    light_size: float = 0.22
    light_energy: float = 560.0
    light_height: float = 2.45
    light_x: float = -0.35
    warm_strength: float = 1.0
    cool_strength: float = 0.0
    subject_scale: tuple[float, float, float] = (0.55, 0.55, 0.9)
    subject_x: float = 0.0
    wall_color: tuple[float, float, float, float] = (0.48, 0.42, 0.68, 1.0)
    floor_color: tuple[float, float, float, float] = (0.34, 0.30, 0.36, 1.0)


def coerce_gobo_settings(settings: GoboLightingSettings | Mapping[str, Any] | None = None) -> GoboLightingSettings:
    if isinstance(settings, GoboLightingSettings):
        return settings
    data = dataclasses.asdict(GoboLightingSettings())
    if settings:
        data.update({key: value for key, value in dict(settings).items() if key in data})
    return GoboLightingSettings(**data)


def gobo_lighting_variants(*, prefix: str = "gobo") -> list[SweepVariant]:
    return named_variants(
        {
            "window_hard": {"pattern": "window", "light_size": 0.08, "blocker_width": 0.09, "warm_strength": 1.0},
            "window_soft": {"pattern": "window", "light_size": 0.8, "blocker_width": 0.09, "warm_strength": 1.0},
            "close_gobo": {"pattern": "slats", "blocker_distance": -1.05, "light_size": 0.18, "blocker_width": 0.08},
            "far_gobo": {"pattern": "slats", "blocker_distance": 0.1, "light_size": 0.18, "blocker_width": 0.08},
            "thin_slats": {"pattern": "slats", "blocker_count": 8, "blocker_width": 0.055, "blocker_gap": 0.24},
            "fat_slats": {"pattern": "slats", "blocker_count": 4, "blocker_width": 0.18, "blocker_gap": 0.42},
            "bands": {"pattern": "bands", "blocker_count": 7, "blocker_width": 0.07, "blocker_gap": 0.24},
            "diagonal": {"pattern": "diagonal", "blocker_count": 6, "blocker_width": 0.07, "blocker_rotation": 24.0},
            "broken": {"pattern": "broken", "blocker_count": 6, "blocker_width": 0.11, "blocker_gap": 0.30},
            "dots": {"pattern": "dots", "blocker_count": 5, "blocker_width": 0.12, "blocker_gap": 0.30},
            "warm": {"pattern": "window", "warm_strength": 1.2, "cool_strength": 0.0, "wall_color": (0.58, 0.34, 0.30, 1.0)},
            "cool": {"pattern": "window", "warm_strength": 0.0, "cool_strength": 1.2, "wall_color": (0.28, 0.34, 0.58, 1.0)},
            "split": {"pattern": "diagonal", "warm_strength": 0.9, "cool_strength": 0.8, "blocker_rotation": -22.0},
            "low_angle": {"pattern": "slats", "light_height": 1.55, "light_size": 0.18, "blocker_width": 0.08},
            "high_angle": {"pattern": "slats", "light_height": 3.35, "light_size": 0.18, "blocker_width": 0.08},
            "monster": {"pattern": "broken", "blocker_distance": 0.15, "light_size": 0.06, "blocker_width": 0.18, "subject_scale": (0.62, 0.62, 1.15)},
        },
        prefix=prefix,
        note="gobo pattern, gel color, distance, and softness scout",
    )


def clear_scene() -> None:
    import bpy

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def look_at(obj: Any, target: tuple[float, float, float]) -> None:
    from mathutils import Vector

    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def _cube(name: str, location, scale, mat: Any, rotation=(0, 0, 0)) -> Any:
    import bpy

    bpy.ops.mesh.primitive_cube_add(size=1, location=location, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(mat)
    return obj


def _shadow_only(obj: Any) -> Any:
    if hasattr(obj, "visible_camera"):
        obj.visible_camera = False
    return obj


def _add_set(settings: GoboLightingSettings) -> None:
    import bpy

    wall = principled_material("matte gobo wall", settings.wall_color, roughness=0.92)
    floor = principled_material("matte gobo floor", settings.floor_color, roughness=0.88)
    subject = principled_material("low poly subject", (0.86, 0.72, 0.52, 1.0), roughness=0.7)

    bpy.ops.mesh.primitive_plane_add(size=5.0, location=(0, 0.25, 0))
    floor_obj = bpy.context.object
    floor_obj.name = "shadow floor"
    floor_obj.data.materials.append(floor)

    bpy.ops.mesh.primitive_plane_add(size=5.0, location=(0, 1.75, 1.7), rotation=(math.pi / 2, 0, 0))
    wall_obj = bpy.context.object
    wall_obj.name = "shadow wall"
    wall_obj.data.materials.append(wall)

    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=0.55, location=(settings.subject_x, 0.62, 0.74))
    obj = bpy.context.object
    obj.name = "faceted subject"
    obj.scale = settings.subject_scale
    obj.data.materials.append(subject)


def _add_gobo(settings: GoboLightingSettings) -> None:
    import bpy

    black = principled_material("black gobo blockers", (0.005, 0.004, 0.004, 1.0), roughness=0.8)
    y = settings.blocker_distance
    count = max(1, int(settings.blocker_count))
    center = (count - 1) * 0.5

    if settings.pattern == "window":
        _shadow_only(_cube("gobo vertical left", (-0.42, y, 1.45), (settings.blocker_width, 0.035, 1.4), black))
        _shadow_only(_cube("gobo vertical right", (0.42, y, 1.45), (settings.blocker_width, 0.035, 1.4), black))
        _shadow_only(_cube("gobo top", (0.0, y, 2.1), (1.0, 0.035, settings.blocker_width), black))
        _shadow_only(_cube("gobo middle", (0.0, y, 1.45), (1.0, 0.035, settings.blocker_width * 0.8), black))
    elif settings.pattern == "bands":
        for index in range(count):
            z = 0.75 + (index - center) * settings.blocker_gap
            _shadow_only(_cube(f"gobo band {index:02d}", (0, y, z), (1.7, 0.035, settings.blocker_width), black))
    elif settings.pattern == "diagonal":
        angle = math.radians(settings.blocker_rotation)
        for index in range(count):
            x = (index - center) * settings.blocker_gap
            _shadow_only(_cube(f"gobo diagonal {index:02d}", (x, y, 1.45), (settings.blocker_width, 0.035, 1.9), black, rotation=(0, angle, 0)))
    elif settings.pattern == "broken":
        for index in range(count):
            x = (index - center) * settings.blocker_gap
            z = 1.25 + 0.28 * math.sin(index * 1.7)
            height = 0.65 + 0.55 * ((index % 3) / 2)
            _shadow_only(_cube(f"gobo broken {index:02d}", (x, y, z), (settings.blocker_width, 0.035, height), black, rotation=(0, math.radians((index % 2) * 18 - 9), 0)))
    elif settings.pattern == "dots":
        for ix in range(count):
            for iz in range(count):
                if (ix + iz) % 2 == 0:
                    x = (ix - center) * settings.blocker_gap
                    z = 0.75 + iz * settings.blocker_gap
                    bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=6, radius=settings.blocker_width, location=(x, y, z))
                    dot = bpy.context.object
                    dot.name = f"gobo dot {ix:02d}_{iz:02d}"
                    dot.scale.y = 0.16
                    dot.data.materials.append(black)
                    _shadow_only(dot)
    else:
        for index in range(count):
            x = (index - center) * settings.blocker_gap
            _shadow_only(_cube(f"gobo slat {index:02d}", (x, y, 1.45), (settings.blocker_width, 0.035, 1.55), black))


def _add_lights(settings: GoboLightingSettings) -> None:
    import bpy

    warm = (1.0, 0.56, 0.28)
    cool = (0.34, 0.56, 1.0)
    for name, offset, color, strength in [
        ("warm gobo key", -0.12, warm, settings.warm_strength),
        ("cool gobo key", 0.18, cool, settings.cool_strength),
    ]:
        if strength <= 0:
            continue
        bpy.ops.object.light_add(type="AREA", location=(settings.light_x + offset, -2.1, settings.light_height))
        light = bpy.context.object
        light.name = name
        light.data.energy = settings.light_energy * strength
        light.data.size = settings.light_size
        light.data.color = color
        look_at(light, (0.0, 1.25, 1.1))

    bpy.ops.object.light_add(type="POINT", location=(1.8, -1.6, 1.7))
    fill = bpy.context.object
    fill.name = "very soft fill"
    fill.data.energy = 18
    fill.data.color = (0.34, 0.36, 0.46)


def _add_camera() -> None:
    import bpy

    bpy.ops.object.camera_add(location=(0.15, -3.75, 1.55))
    cam = bpy.context.object
    cam.name = GOBO_CAMERA
    look_at(cam, (0.0, 1.05, 1.05))
    cam.data.lens = 42
    bpy.context.scene.camera = cam


def build_gobo_lighting_scene(settings: GoboLightingSettings | Mapping[str, Any] | None = None) -> None:
    import bpy

    gobo_settings = coerce_gobo_settings(settings)
    clear_scene()
    world = bpy.context.scene.world or bpy.data.worlds.new("gobo lighting world")
    bpy.context.scene.world = world
    world.color = (0.012, 0.011, 0.018)
    _add_set(gobo_settings)
    _add_gobo(gobo_settings)
    _add_lights(gobo_settings)
    _add_camera()
