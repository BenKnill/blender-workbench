import json
import tempfile
import unittest
from pathlib import Path

import blender_workbench.render_passes as pass_module
from blender_workbench.render_passes import (
    PassDiagnosticReport,
    PassSpec,
    PassTile,
    coerce_pass_specs,
    default_pass_specs,
    format_pass_diagnostic_readme,
    pass_tiles_to_results,
    write_pass_diagnostic_metadata,
    write_pass_diagnostic_outputs,
    write_pass_diagnostic_readme,
)
from blender_workbench.sweep import RenderConfig, TileSpec


class RenderPassTests(unittest.TestCase):
    def test_default_pass_specs_include_graceful_pass_flags(self):
        specs = default_pass_specs()
        names = [spec.name for spec in specs]

        self.assertIn("combined", names)
        self.assertIn("depth", names)
        self.assertIn("normal", names)
        self.assertEqual(next(spec for spec in specs if spec.name == "combined").enable_flags, ())
        self.assertIn("use_pass_z", next(spec for spec in specs if spec.name == "depth").enable_flags)

    def test_coerce_pass_specs_accepts_mappings(self):
        specs = coerce_pass_specs(
            [
                {"name": "beauty", "label": "beauty", "outputs": ["Image", "Combined"]},
                {"name": "mist", "output": "Mist", "enable_flag": "use_pass_mist"},
            ]
        )

        self.assertEqual(specs[0], PassSpec("beauty", "beauty", ("Image", "Combined")))
        self.assertEqual(specs[1].outputs, ("Mist",))
        self.assertEqual(specs[1].enable_flags, ("use_pass_mist",))
        with self.assertRaisesRegex(ValueError, "missing name"):
            coerce_pass_specs([{"outputs": ["Image"]}])

    def test_pass_metadata_and_readme_record_unavailable_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            report = PassDiagnosticReport(
                title="Pass Test",
                tiles=(
                    PassTile("combined", "combined", output="Image", path="out/passes/combined_0001.png"),
                    PassTile("normal", "normal", available=False, warning="not available"),
                ),
                source_scene_settings={"scene": "fixed"},
                render_config=RenderConfig(samples=3),
                notes=("Before look sweeps.",),
                warnings=("normal: no Render Layers output matching Normal",),
                render_seconds=1.25,
            )
            metadata_path = write_pass_diagnostic_metadata(report, out_dir)
            readme_path = write_pass_diagnostic_readme(report, out_dir)
            metadata = json.loads(metadata_path.read_text())
            readme = readme_path.read_text()

        self.assertEqual(metadata["mode"], "render_pass_diagnostics")
        self.assertTrue(metadata["workflow"]["before_compositor_look_sweep"])
        self.assertEqual(metadata["passes"][0]["output"], "Image")
        self.assertEqual(metadata["unavailable_passes"][0]["name"], "normal")
        self.assertIn("normal; unavailable", readme)
        self.assertIn("Before look sweeps.", readme)

    def test_write_outputs_can_create_contact_sheet_metadata(self):
        original_write_contact_sheet = pass_module.write_contact_sheet

        def fake_contact_sheet(_results, _root, out_path, _tile):
            out_path.write_text("contact")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_dir = root / "examples/output/pass_demo"
            report = PassDiagnosticReport(
                title="Pass Demo",
                tiles=(PassTile("combined", "combined", output="Image", path="examples/output/pass_demo/passes/combined_0001.png"),),
            )
            pass_module.write_contact_sheet = fake_contact_sheet
            try:
                updated = write_pass_diagnostic_outputs(report, out_dir=out_dir, root=root, tile=TileSpec.filmstrip(columns=1))
            finally:
                pass_module.write_contact_sheet = original_write_contact_sheet

            metadata = json.loads((out_dir / "metadata.json").read_text())

        self.assertEqual(updated.contact_sheet, "examples/output/pass_demo/contact_sheet.png")
        self.assertEqual(metadata["contact_sheet"], "examples/output/pass_demo/contact_sheet.png")
        self.assertEqual(pass_tiles_to_results(updated.tiles, root=root)[0].tags, ("render_pass",))
        self.assertIn("Render-pass diagnostic", format_pass_diagnostic_readme(updated))


if __name__ == "__main__":
    unittest.main()
