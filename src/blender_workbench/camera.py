from __future__ import annotations

import math
from typing import Any


def camera_distance_for_matching_framing(lens_mm: float, *, base_lens_mm: float = 45.0, base_distance: float = 4.0) -> float:
    """Approximate distance that keeps subject size similar as lens changes."""
    if base_lens_mm <= 0:
        raise ValueError("base_lens_mm must be positive")
    if lens_mm <= 0:
        raise ValueError("lens_mm must be positive")
    return base_distance * (lens_mm / base_lens_mm)


def orbit_location(
    *,
    target: tuple[float, float, float],
    distance: float,
    yaw_degrees: float = 0.0,
    pitch_degrees: float = 10.0,
) -> tuple[float, float, float]:
    yaw = math.radians(yaw_degrees)
    pitch = math.radians(pitch_degrees)
    horizontal = distance * math.cos(pitch)
    return (
        target[0] + math.sin(yaw) * horizontal,
        target[1] - math.cos(yaw) * horizontal,
        target[2] + math.sin(pitch) * distance,
    )


def look_at(obj: Any, target: tuple[float, float, float]) -> None:
    from mathutils import Vector

    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def add_orbit_camera(
    *,
    name: str,
    target: tuple[float, float, float],
    distance: float,
    lens_mm: float,
    yaw_degrees: float = 0.0,
    pitch_degrees: float = 10.0,
    roll_degrees: float = 0.0,
) -> Any:
    import bpy

    location = orbit_location(target=target, distance=distance, yaw_degrees=yaw_degrees, pitch_degrees=pitch_degrees)
    bpy.ops.object.camera_add(location=location)
    cam = bpy.context.object
    cam.name = name
    look_at(cam, target)
    if roll_degrees:
        cam.rotation_euler.rotate_axis("Z", math.radians(roll_degrees))
    cam.data.lens = lens_mm
    bpy.context.scene.camera = cam
    return cam
