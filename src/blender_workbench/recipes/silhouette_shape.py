from __future__ import annotations

import dataclasses
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from blender_workbench.camera import add_orbit_camera
from blender_workbench.materials import principled_material
from blender_workbench.sweep import SweepVariant, named_variants


SILHOUETTE_SHAPE_CAMERA = "silhouette_shape_camera"


@dataclass(frozen=True)
class SilhouetteShapeSettings:
    primary_scale: tuple[float, float, float] = (0.86, 0.58, 1.18)
    secondary_scale: tuple[float, float, float] = (0.42, 0.38, 0.72)
    head_scale: float = 0.34
    arm_span: float = 0.78
    lean: float = 0.0
    stance: float = 0.42
    crop_scale: float = 1.0


def coerce_silhouette_shape_settings(settings: SilhouetteShapeSettings | Mapping[str, Any] | None = None) -> SilhouetteShapeSettings:
    if isinstance(settings, SilhouetteShapeSettings):
        return settings
    data = dataclasses.asdict(SilhouetteShapeSettings())
    if settings:
        data.update({key: value for key, value in dict(settings).items() if key in data})
    return SilhouetteShapeSettings(**data)


def silhouette_shape_variants(*, prefix: str = "sil") -> list[SweepVariant]:
    return named_variants(
        {
            "spindly": {
                "primary_scale": (0.52, 0.42, 1.42),
                "secondary_scale": (0.24, 0.28, 1.02),
                "arm_span": 1.05,
                "stance": 0.28,
            },
            "blocky": {
                "primary_scale": (1.02, 0.64, 0.92),
                "secondary_scale": (0.64, 0.40, 0.62),
                "head_scale": 0.38,
                "stance": 0.58,
            },
            "swept": {
                "primary_scale": (0.74, 0.50, 1.08),
                "secondary_scale": (0.34, 0.34, 0.72),
                "arm_span": 1.24,
                "lean": -12.0,
                "stance": 0.36,
            },
            "squat": {
                "primary_scale": (1.12, 0.68, 0.70),
                "secondary_scale": (0.48, 0.42, 0.46),
                "head_scale": 0.30,
                "stance": 0.72,
            },
            "tall": {
                "primary_scale": (0.66, 0.45, 1.66),
                "secondary_scale": (0.32, 0.30, 1.10),
                "head_scale": 0.28,
                "arm_span": 0.62,
                "stance": 0.24,
            },
            "cropped_fail": {
                "primary_scale": (1.18, 0.70, 1.72),
                "secondary_scale": (0.70, 0.42, 0.96),
                "head_scale": 0.44,
                "arm_span": 1.50,
                "crop_scale": 1.42,
            },
        },
        base=dataclasses.asdict(SilhouetteShapeSettings()),
        prefix=prefix,
        note="blind silhouette scout: judge outline before material polish",
    )


def clear_scene() -> None:
    import bpy

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def _cube(name: str, location, scale, mat, rotation=(0.0, 0.0, 0.0)) -> Any:
    import bpy

    bpy.ops.mesh.primitive_cube_add(size=1, location=location, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(mat)
    return obj


def _add_silhouette(settings: SilhouetteShapeSettings) -> None:
    import bpy

    black = principled_material("flat black silhouette", (0.01, 0.01, 0.012, 1.0), roughness=0.95)
    black.diffuse_color = (0.005, 0.005, 0.006, 1.0)
    gray = principled_material("blind board background", (0.86, 0.86, 0.83, 1.0), roughness=1.0)
    gray.diffuse_color = (0.86, 0.86, 0.83, 1.0)
    lean = math.radians(settings.lean)

    bpy.ops.mesh.primitive_plane_add(size=5.0, location=(0.0, 1.0, 1.1), rotation=(math.pi / 2, 0.0, 0.0))
    bg = bpy.context.object
    bg.name = "plain value background"
    bg.data.materials.append(gray)

    _cube("primary mass", (0.0, 0.0, 0.88), settings.primary_scale, black, rotation=(0.0, 0.0, lean))
    _cube("secondary tail mass", (-0.24, 0.02, 0.46), settings.secondary_scale, black, rotation=(0.0, 0.0, lean * 0.5))

    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=settings.head_scale, location=(0.10 + math.sin(lean) * 0.30, -0.02, 1.70))
    head = bpy.context.object
    head.name = "head read mass"
    head.scale = (1.0, 0.82, 1.0)
    head.data.materials.append(black)

    _cube("left read limb", (-settings.arm_span * 0.5, -0.02, 1.02), (settings.arm_span, 0.10, 0.11), black, rotation=(0.0, 0.0, lean - 0.22))
    _cube("right read limb", (settings.arm_span * 0.42, -0.02, 0.88), (settings.arm_span * 0.76, 0.10, 0.10), black, rotation=(0.0, 0.0, lean + 0.18))
    _cube("left stance", (-settings.stance, -0.02, 0.12), (0.16, 0.12, 0.34), black, rotation=(0.0, 0.0, -0.10))
    _cube("right stance", (settings.stance, -0.02, 0.12), (0.16, 0.12, 0.34), black, rotation=(0.0, 0.0, 0.10))


def _configure_world() -> None:
    import bpy

    world = bpy.context.scene.world or bpy.data.worlds.new("silhouette shape world")
    bpy.context.scene.world = world
    world.color = (0.86, 0.86, 0.83)


def _add_camera(settings: SilhouetteShapeSettings) -> None:
    cam = add_orbit_camera(
        name=SILHOUETTE_SHAPE_CAMERA,
        target=(0.0, 0.0, 0.92),
        distance=6.5,
        lens_mm=55.0,
        yaw_degrees=0.0,
        pitch_degrees=0.0,
    )
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 2.95 / max(0.55, settings.crop_scale)


def build_silhouette_shape_scene(settings: SilhouetteShapeSettings | Mapping[str, Any] | None = None) -> None:
    shape_settings = coerce_silhouette_shape_settings(settings)
    clear_scene()
    _configure_world()
    _add_silhouette(shape_settings)
    _add_camera(shape_settings)
