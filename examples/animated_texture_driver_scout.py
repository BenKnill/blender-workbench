from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from blender_workbench.camera import add_orbit_camera, look_at
from blender_workbench.materials import emission_material, principled_material, transparent_emission_material
from blender_workbench.presets import RENDER_PRESETS, TILE_PRESETS
from blender_workbench.sweep import FrameSample, render_frame_sweep


OUT = ROOT / "examples" / "output" / "animated_texture_driver_scout"
DRIVER_CAMERA = "driver_filmstrip_camera"
FPS = 24.0
FRAME_NUMBERS = (1, 12, 24, 36, 48)


@dataclass(frozen=True)
class DriverSceneSettings:
    driver_speed: float = 0.055
    band_width: float = 0.18
    band_strength: float = 2.8
    gate_alpha: float = 0.22


def _script_args(argv: list[str] | None = None) -> list[str]:
    values = list(sys.argv[1:] if argv is None else argv)
    if "--" in values:
        return values[values.index("--") + 1 :]
    return values


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render an animated texture/driver frame-sampled filmstrip.")
    parser.add_argument("--pick-frame", type=int, help="render one selected frame with the hero profile")
    parser.add_argument("--hero-samples", type=int, default=96, help="Cycles samples for --pick-frame")
    args, _unknown = parser.parse_known_args(_script_args(argv))
    return args


def driver_values_for_frame(frame: int, settings: DriverSceneSettings | None = None) -> dict[str, float]:
    values = settings or DriverSceneSettings()
    offset = (frame - 24) * values.driver_speed
    phase = (frame - min(FRAME_NUMBERS)) / max(1, max(FRAME_NUMBERS) - min(FRAME_NUMBERS))
    return {
        "frame_offset_x": round(offset, 3),
        "texture_phase": round(phase, 3),
        "driver_speed": values.driver_speed,
    }


def frame_samples(frames: tuple[int, ...] = FRAME_NUMBERS, settings: DriverSceneSettings | None = None) -> tuple[FrameSample, ...]:
    return tuple(
        FrameSample(
            frame=frame,
            label=f"f{frame}",
            note="driver checkpoints for texture-band motion",
            driver_values=driver_values_for_frame(frame, settings),
        )
        for frame in frames
    )


def clear_scene() -> None:
    import bpy

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def _cube(name: str, location, scale, mat, rotation=(0.0, 0.0, 0.0)):
    import bpy

    bpy.ops.mesh.primitive_cube_add(size=1, location=location, rotation=rotation)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(mat)
    return obj


def _add_frame_driver(obj, speed: float) -> None:
    import bpy

    fcurve = obj.driver_add("location", 0)
    driver = fcurve.driver
    driver.type = "SCRIPTED"
    variable = driver.variables.new()
    variable.name = "frame"
    variable.targets[0].id_type = "SCENE"
    variable.targets[0].id = bpy.context.scene
    variable.targets[0].data_path = "frame_current"
    driver.expression = f"(frame - 24) * {speed:.6f}"


def build_driver_scene(settings: DriverSceneSettings | None = None) -> None:
    import bpy

    values = settings or DriverSceneSettings()
    clear_scene()
    scene = bpy.context.scene
    scene.frame_start = min(FRAME_NUMBERS)
    scene.frame_end = max(FRAME_NUMBERS)
    scene.render.fps = int(FPS)

    world = scene.world or bpy.data.worlds.new("animated driver world")
    scene.world = world
    world.color = (0.012, 0.014, 0.02)

    floor_mat = principled_material("driver matte floor", (0.16, 0.17, 0.19, 1.0), roughness=0.84)
    gate_mat = transparent_emission_material("driver timing gates", (0.32, 0.62, 1.0, 1.0), 0.8, values.gate_alpha)
    band_mat = emission_material("animated texture band", (1.0, 0.68, 0.28, 1.0), values.band_strength)
    marker_mat = principled_material("driver neutral marker", (0.72, 0.70, 0.64, 1.0), roughness=0.58)

    bpy.ops.mesh.primitive_plane_add(size=4.6, location=(0, 0, -0.03))
    floor = bpy.context.object
    floor.name = "driver matte floor"
    floor.data.materials.append(floor_mat)

    for index, x in enumerate((-1.2, 0.0, 1.2), start=1):
        _cube(f"timing gate {index}", (x, 0.18, 0.52), (0.035, 0.02, 0.95), gate_mat)

    band = _cube(
        "animated texture driver band",
        (driver_values_for_frame(1, values)["frame_offset_x"], -0.05, 0.52),
        (values.band_width, 0.035, 0.95),
        band_mat,
        rotation=(0.0, 0.0, math.radians(3.0)),
    )
    _add_frame_driver(band, values.driver_speed)

    _cube("driver scale marker", (0.0, 0.46, 0.14), (1.45, 0.12, 0.12), marker_mat)

    bpy.ops.object.light_add(type="AREA", location=(0.4, -2.2, 2.6))
    light = bpy.context.object
    light.name = "driver softbox"
    light.data.energy = 420
    light.data.size = 3.0
    look_at(light, (0, 0.2, 0.45))

    add_orbit_camera(
        name=DRIVER_CAMERA,
        target=(0.0, 0.18, 0.44),
        distance=4.2,
        lens_mm=58.0,
        yaw_degrees=0.0,
        pitch_degrees=9.0,
    )


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    scene_settings = DriverSceneSettings()
    if args.pick_frame is not None:
        selected = frame_samples((args.pick_frame,), scene_settings)
        config = replace(
            RENDER_PRESETS["hero_check"],
            samples=args.hero_samples,
            camera_name=DRIVER_CAMERA,
            tile=TILE_PRESETS["filmstrip"],
        )
        render_frame_sweep(
            frame_samples=selected,
            build_scene=build_driver_scene,
            out_dir=OUT / "selected_frame" / f"frame_{args.pick_frame:04d}",
            root=ROOT,
            scene_settings=scene_settings,
            fps=FPS,
            config=config,
            postprocess=None,
            title="Animated Texture Driver Selected Frame",
            notes=["Heavier single-frame check after reviewing the driver filmstrip."],
        )
        return

    config = replace(
        RENDER_PRESETS["cycles_preview"],
        resolution_x=620,
        resolution_y=360,
        samples=24,
        max_bounces=4,
        camera_name=DRIVER_CAMERA,
        tile=TILE_PRESETS["filmstrip"],
    )
    render_frame_sweep(
        frame_samples=frame_samples(settings=scene_settings),
        build_scene=build_driver_scene,
        out_dir=OUT,
        root=ROOT,
        scene_settings=scene_settings,
        fps=FPS,
        config=config,
        postprocess=None,
        title="Animated Texture Driver Scout",
        notes=[
            "Frame-sampled filmstrip for a driven texture-band marker.",
            "Use this when the question is temporal motion or driver scale, not unrelated named cases.",
        ],
    )


if __name__ == "__main__":
    main()
