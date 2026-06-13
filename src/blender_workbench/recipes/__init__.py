"""Optional scene recipes built on the generic workbench helpers."""

from .rocket_plume import (
    ROCKET_PLUME_CAMERA,
    RocketPlumeSettings,
    build_rocket_plume_scene,
    coerce_rocket_plume_settings,
    rocket_plume_scout_variants,
)

__all__ = [
    "ROCKET_PLUME_CAMERA",
    "RocketPlumeSettings",
    "build_rocket_plume_scene",
    "coerce_rocket_plume_settings",
    "rocket_plume_scout_variants",
]
