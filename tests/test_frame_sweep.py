import json
import tempfile
import unittest
from pathlib import Path

import blender_workbench.sweep as sweep_module
from blender_workbench.sweep import FrameSample, RenderConfig, RenderResult, TileSpec, coerce_frame_samples, render_frame_sweep


class FrameSweepTests(unittest.TestCase):
    def test_coerce_frame_samples_accepts_ints_mappings_and_samples(self):
        samples = coerce_frame_samples(
            [
                1,
                {"frame": 12, "label": "mid", "driver_values": {"phase": 0.5}},
                FrameSample(frame=24, note="hero checkpoint"),
            ]
        )

        self.assertEqual([sample.frame for sample in samples], [1, 12, 24])
        self.assertEqual(samples[1].label, "mid")
        self.assertEqual(samples[1].driver_values["phase"], 0.5)
        self.assertEqual(samples[2].note, "hero checkpoint")

    def test_render_frame_sweep_records_metadata_without_blender(self):
        build_calls = []
        set_frames = []
        original_render_variant = sweep_module._render_variant
        original_write_contact_sheet = sweep_module.write_contact_sheet
        original_write_sweep_diagnostics = sweep_module.write_sweep_diagnostics

        def fake_render_variant(**kwargs):
            kwargs["build_scene"](kwargs["variant"].settings)
            raw = kwargs["out_dir"] / f"{kwargs['variant'].name}.frame.raw.png"
            raw.write_text("image")
            return RenderResult(
                name=kwargs["variant"].name,
                raw=str(raw.relative_to(kwargs["root"])),
                finished=None,
                settings=kwargs["variant"].settings,
                label=kwargs["variant"].label,
                note=kwargs["variant"].note,
                tags=kwargs["variant"].tags,
                engine=kwargs["config"].engine,
                camera_name=kwargs["config"].camera_name,
                fingerprint={"schema": 1, "fingerprint": f"{kwargs['variant'].name}-fp"},
            )

        def fake_contact_sheet(_results, _root, out_path, _tile, **_kwargs):
            out_path.write_text("contact")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_dir = root / "examples/output/frame_demo"
            sweep_module._render_variant = fake_render_variant
            sweep_module.write_contact_sheet = fake_contact_sheet
            sweep_module.write_sweep_diagnostics = lambda *_args, **_kwargs: {"warnings": []}
            try:
                results = render_frame_sweep(
                    frame_samples=[
                        FrameSample(frame=1, label="start", driver_values={"offset": -1.0}),
                        FrameSample(frame=24, label="middle", driver_values={"offset": 0.0}),
                    ],
                    build_scene=lambda settings: build_calls.append(settings),
                    set_frame=lambda frame: set_frames.append(frame),
                    out_dir=out_dir,
                    root=root,
                    scene_settings={"driver_speed": 0.055},
                    fps=24,
                    config=RenderConfig(camera_name="FrameCamera", tile=TileSpec.filmstrip(columns=2)),
                    postprocess=None,
                    title="Frame Demo",
                    notes=["Temporal test."],
                )
            finally:
                sweep_module._render_variant = original_render_variant
                sweep_module.write_contact_sheet = original_write_contact_sheet
                sweep_module.write_sweep_diagnostics = original_write_sweep_diagnostics

            metadata = json.loads((out_dir / "metadata.json").read_text())
            readme = (out_dir / "README.md").read_text()

        self.assertEqual(build_calls, [{"driver_speed": 0.055}])
        self.assertEqual(set_frames, [1, 24])
        self.assertEqual([result.label for result in results], ["start", "middle"])
        self.assertEqual(metadata["mode"], "frame_sweep")
        self.assertEqual(metadata["fps"], 24)
        self.assertEqual(metadata["source_scene_settings"], {"driver_speed": 0.055})
        self.assertEqual(metadata["workflow"]["stage"], "frame_sweep")
        self.assertTrue(metadata["workflow"]["temporal_board_not_static_variant_grid"])
        self.assertEqual(metadata["frames"][1]["frame"], 24)
        self.assertEqual(metadata["frames"][1]["time_seconds"], 0.9583)
        self.assertEqual(metadata["frames"][1]["driver_values"], {"offset": 0.0})
        self.assertEqual(metadata["frames"][1]["result"]["raw"], "examples/output/frame_demo/frame_0024.frame.raw.png")
        self.assertIn("Frame-sampled filmstrip", readme)
        self.assertIn("Temporal test.", readme)


if __name__ == "__main__":
    unittest.main()
