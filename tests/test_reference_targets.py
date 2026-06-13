import json
import tempfile
import unittest
from pathlib import Path

import blender_workbench.sweep as sweep_module
from blender_workbench.sweep import (
    ReferenceTarget,
    RenderConfig,
    RenderResult,
    SweepVariant,
    TileSpec,
    render_selected_variant,
    render_sweep,
    write_contact_sheet,
)


class ReferenceTargetTests(unittest.TestCase):
    def test_render_sweep_records_reference_targets_in_metadata_and_readme(self):
        original_render_variant = sweep_module._render_variant
        original_write_contact_sheet = sweep_module.write_contact_sheet

        def fake_render_variant(**kwargs):
            raw = kwargs["out_dir"] / f"{kwargs['variant'].name}.raw.png"
            raw.write_text("image")
            return RenderResult(name=kwargs["variant"].name, raw=str(raw.relative_to(kwargs["root"])), finished=None, settings={})

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_dir = root / "examples/output/demo"
            reference = root / "refs/plume.png"
            reference.parent.mkdir(parents=True)
            reference.write_text("image")
            sweep_module._render_variant = fake_render_variant
            sweep_module.write_contact_sheet = lambda *_args, **_kwargs: None
            try:
                render_sweep(
                    variants=[SweepVariant("wide", {})],
                    build_scene=lambda _settings: None,
                    out_dir=out_dir,
                    root=root,
                    config=RenderConfig(),
                    postprocess=None,
                    reference_targets=[
                        ReferenceTarget(
                            path="refs/plume.png",
                            source_type="frame",
                            caption="SpaceX plume keyframe",
                            frame=12,
                            match=("soft gray shell", "blue-white core"),
                        )
                    ],
                )
            finally:
                sweep_module._render_variant = original_render_variant
                sweep_module.write_contact_sheet = original_write_contact_sheet

            metadata = json.loads((out_dir / "metadata.json").read_text())
            readme = (out_dir / "README.md").read_text()

        self.assertEqual(metadata["reference_targets"][0]["path"], "refs/plume.png")
        self.assertEqual(metadata["reference_targets"][0]["frame"], 12)
        self.assertEqual(metadata["contact_sheet"]["reference_panels"], 1)
        self.assertIn("Reference targets", readme)
        self.assertIn("SpaceX plume keyframe", readme)
        self.assertIn("best matches the target criteria", readme)

    def test_contact_sheet_command_puts_reference_panel_first(self):
        calls = []
        original_which = sweep_module.shutil.which
        original_run = sweep_module.subprocess.run

        def fake_run(command, check):
            calls.append(command)
            Path(command[-1]).write_text("image")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_dir = root / "out"
            out_dir.mkdir()
            ref = root / "refs/ref.png"
            raw = root / "out/wide.raw.png"
            ref.parent.mkdir()
            ref.write_text("image")
            raw.write_text("image")
            sweep_module.shutil.which = lambda name: "/usr/bin/magick" if name == "magick" else None
            sweep_module.subprocess.run = fake_run
            try:
                write_contact_sheet(
                    [RenderResult("wide", "out/wide.raw.png", None, {})],
                    root,
                    out_dir / "contact_sheet.png",
                    TileSpec(width=64, height=64, label_height=12, label_max_chars=80),
                    reference_targets=[ReferenceTarget(path="refs/ref.png", caption="target panel")],
                )
            finally:
                sweep_module.shutil.which = original_which
                sweep_module.subprocess.run = original_run

        self.assertIn(str(ref), calls[0])
        self.assertIn("ref: target panel", calls[0])
        self.assertIn(str(raw), calls[1])

    def test_selected_render_writes_reference_attempt_metadata_without_blender(self):
        original_render_variant = sweep_module._render_variant
        original_which = sweep_module.shutil.which
        original_run = sweep_module.subprocess.run

        def fake_render_variant(**kwargs):
            raw = kwargs["out_dir"] / f"{kwargs['variant'].name}.hero.raw.png"
            raw.write_text("image")
            return RenderResult(name=kwargs["variant"].name, raw=str(raw.relative_to(kwargs["root"])), finished=None, settings={})

        def fake_run(command, check):
            Path(command[-1]).write_text("comparison")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_dir = root / "examples/output/demo/selected/wide"
            ref = root / "refs/ref.png"
            ref.parent.mkdir(parents=True)
            ref.write_text("image")
            sweep_module._render_variant = fake_render_variant
            sweep_module.shutil.which = lambda name: "/usr/bin/magick" if name == "magick" else None
            sweep_module.subprocess.run = fake_run
            try:
                render_selected_variant(
                    variants=[SweepVariant("wide", {})],
                    pick="wide",
                    build_scene=lambda _settings: None,
                    out_dir=out_dir,
                    root=root,
                    postprocess=None,
                    reference_targets=[{"path": "refs/ref.png", "caption": "target"}],
                )
            finally:
                sweep_module._render_variant = original_render_variant
                sweep_module.shutil.which = original_which
                sweep_module.subprocess.run = original_run

            selected = json.loads((out_dir / "selected.json").read_text())
            readme = (out_dir / "README.md").read_text()

        self.assertEqual(selected["reference_attempt"]["path"], "examples/output/demo/selected/wide/reference_attempt.png")
        self.assertEqual(selected["reference_targets"][0]["caption"], "target")
        self.assertIn("Reference comparison", readme)


if __name__ == "__main__":
    unittest.main()
