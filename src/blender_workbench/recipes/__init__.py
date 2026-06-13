"""Optional scene recipes built on the generic workbench helpers."""

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

__all__ = [
    "GOBO_CAMERA",
    "GoboLightingSettings",
    "ROCKET_PLUME_CAMERA",
    "RocketPlumeSettings",
    "SUBSURFACE_CAMERA",
    "SubsurfaceSettings",
    "build_gobo_lighting_scene",
    "build_rocket_plume_scene",
    "build_subsurface_scene",
    "coerce_gobo_settings",
    "coerce_rocket_plume_settings",
    "coerce_subsurface_settings",
    "gobo_lighting_variants",
    "rocket_plume_scout_variants",
    "rocket_plume_texture_variants",
    "subsurface_variants",
]
