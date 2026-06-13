import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

import blender_workbench.sweep as sweep_module
from blender_workbench.image_diagnostics import analyze_sweep_images
from blender_workbench.sweep import RenderResult, SweepVariant, render_sweep


def write_gray_png(path: Path, rows: list[list[int]]) -> None:
    height = len(rows)
    width = len(rows[0])

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + bytes(row) for row in rows)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk("IHDR".encode(), struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))
        + chunk("IDAT".encode(), zlib.compress(raw))
        + chunk("IEND".encode(), b"")
    )


class ImageDiagnosticsTests(unittest.TestCase):
    def test_identical_dark_tiles_report_low_spread_and_readability(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "first.png"
            second = root / "second.png"
            rows = [[5, 5, 5, 5] for _ in range(4)]
            write_gray_png(first, rows)
            write_gray_png(second, rows)

            diagnostics = analyze_sweep_images([("first", first), ("second", second)])

        self.assertIn("low_visual_spread", diagnostics["warnings"])
        self.assertIn("all_tiles_low_readability", diagnostics["warnings"])
        self.assertIn("too_dark", diagnostics["tiles"][0]["warnings"])
        self.assertIn("low_contrast", diagnostics["tiles"][0]["warnings"])
        self.assertEqual(diagnostics["pairwise"]["mean_rmse"], 0.0)
        self.assertIn("Diagnostics steer human review", diagnostics["stance"])

    def test_bright_blank_tile_reports_blowout(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "white.png"
            write_gray_png(path, [[255, 255], [255, 255]])

            diagnostics = analyze_sweep_images([("white", path)])

        self.assertIn("too_bright", diagnostics["tiles"][0]["warnings"])
        self.assertIn("low_contrast", diagnostics["tiles"][0]["warnings"])

    def test_render_sweep_writes_diagnostics_metadata_and_readme_without_blender(self):
        original_render_variant = sweep_module._render_variant
        original_write_contact_sheet = sweep_module.write_contact_sheet

        def fake_render_variant(**kwargs):
            variant = kwargs["variant"]
            raw = kwargs["out_dir"] / f"{variant.name}.raw.png"
            value = int(variant.settings["value"])
            write_gray_png(raw, [[value, value], [value, value]])
            return RenderResult(
                name=variant.name,
                raw=str(raw.relative_to(kwargs["root"])),
                finished=None,
                settings=variant.settings,
            )

        def fake_contact_sheet(_results, _root, out_path, _tile):
            write_gray_png(out_path, [[12, 12], [12, 12]])

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_dir = root / "examples/output/demo"
            sweep_module._render_variant = fake_render_variant
            sweep_module.write_contact_sheet = fake_contact_sheet
            try:
                render_sweep(
                    variants=[
                        SweepVariant("a", {"value": 80}),
                        SweepVariant("b", {"value": 81}),
                        SweepVariant("c", {"value": 82}),
                    ],
                    build_scene=lambda _settings: None,
                    out_dir=out_dir,
                    root=root,
                    postprocess=None,
                    title="Demo Diagnostics",
                )
            finally:
                sweep_module._render_variant = original_render_variant
                sweep_module.write_contact_sheet = original_write_contact_sheet

            diagnostics = json.loads((out_dir / "diagnostics.json").read_text())
            metadata = json.loads((out_dir / "metadata.json").read_text())
            readme = (out_dir / "README.md").read_text()

        self.assertIn("low_visual_spread", diagnostics["warnings"])
        self.assertEqual(metadata["diagnostics"]["warnings"], diagnostics["warnings"])
        self.assertIn("Board diagnostics", readme)
        self.assertIn("Diagnostics steer review", readme)


if __name__ == "__main__":
    unittest.main()
