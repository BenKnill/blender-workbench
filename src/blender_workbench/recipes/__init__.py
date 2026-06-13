"""Optional scene recipes built on the generic workbench helpers."""

from .camera_perspective import (
    CAMERA_PERSPECTIVE_CAMERA,
    CameraPerspectiveSettings,
    build_camera_perspective_scene,
    camera_perspective_variants,
    coerce_camera_perspective_settings,
)
from .gobo_lighting import GOBO_CAMERA, GoboLightingSettings, build_gobo_lighting_scene, coerce_gobo_settings, gobo_lighting_variants
from .rocket_plume import (
    ROCKET_PLUME_CAMERA,
    RocketPlumeSettings,
    build_rocket_plume_scene,
    coerce_rocket_plume_settings,
    rocket_plume_scout_variants,
    rocket_plume_texture_variants,
)
from .subsurface import (
    SUBSURFACE_CAMERA,
    SubsurfaceSettings,
    build_subsurface_scene,
    coerce_subsurface_settings,
    subsurface_variants,
)
from .transparency import (
    TRANSPARENCY_CAMERA,
    TransparencySettings,
    build_transparency_scene,
    coerce_transparency_settings,
    transparency_variants,
)

__all__ = [
    "CAMERA_PERSPECTIVE_CAMERA",
    "CameraPerspectiveSettings",
    "GOBO_CAMERA",
    "GoboLightingSettings",
    "ROCKET_PLUME_CAMERA",
    "RocketPlumeSettings",
    "SUBSURFACE_CAMERA",
    "SubsurfaceSettings",
    "TRANSPARENCY_CAMERA",
    "TransparencySettings",
    "build_camera_perspective_scene",
    "build_gobo_lighting_scene",
    "build_rocket_plume_scene",
    "build_subsurface_scene",
    "build_transparency_scene",
    "camera_perspective_variants",
    "coerce_camera_perspective_settings",
    "coerce_gobo_settings",
    "coerce_rocket_plume_settings",
    "coerce_subsurface_settings",
    "coerce_transparency_settings",
    "gobo_lighting_variants",
    "rocket_plume_scout_variants",
    "rocket_plume_texture_variants",
    "subsurface_variants",
    "transparency_variants",
]
