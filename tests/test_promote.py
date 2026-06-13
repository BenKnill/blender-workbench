import json
import tempfile
import unittest
from pathlib import Path

import blender_workbench.promote as promote_module
from blender_workbench.promote import (
    import_recipe_callable,
    load_sweep_metadata,
    load_sweep_variants,
    metadata_path_for_sweep,
    promote_from_metadata,
    safe_variant_name,
    select_metadata_variant,
)
from blender_workbench.review_log import write_review_log
from blender_workbench.sweep import RenderResult


class PromoteTests(unittest.TestCase):
    def test_load_sweep_variants_from_metadata_dir_or_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            sweep_dir = Path(tmp)
            metadata = {
                "variants": [
                    {
                        "name": "wide_shell",
                        "label": "wide",
                        "note": "winner",
                        "role": "aesthetic_extreme",
                        "tags": ["glow_edge"],
                        "settings": {"width": 1.4},
                    },
                    {"name": "soft_fill", "label": "soft", "settings": {"fill": 0.8}},
                ]
            }
            (sweep_dir / "metadata.json").write_text(json.dumps(metadata))

            self.assertEqual(metadata_path_for_sweep(sweep_dir), sweep_dir / "metadata.json")
            variants = load_sweep_variants(sweep_dir)
            same_variants = load_sweep_variants(sweep_dir / "metadata.json")

        self.assertEqual([variant.name for variant in variants], ["wide_shell", "soft_fill"])
        self.assertEqual(same_variants[0].settings, {"width": 1.4})
        self.assertEqual(variants[0].label, "wide")
        self.assertEqual(variants[0].note, "winner")
        self.assertEqual(variants[0].role, "aesthetic_extreme")
        self.assertEqual(variants[0].tags, ("glow_edge",))
        self.assertEqual(variants[1].role, "candidate")

    def test_select_metadata_variant_accepts_index_name_or_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            sweep_dir = Path(tmp)
            (sweep_dir / "metadata.json").write_text(
                json.dumps(
                    {
                        "variants": [
                            {"name": "wide_shell", "label": "wide", "settings": {"width": 1.4}},
                            {"name": "soft_fill", "label": "soft", "settings": {"fill": 0.8}},
                        ]
                    }
                )
            )

            by_index = select_metadata_variant(sweep_dir, "2")
            by_label = select_metadata_variant(sweep_dir, "wide")

        self.assertEqual(by_index.name, "soft_fill")
        self.assertEqual(by_label.name, "wide_shell")

    def test_load_sweep_metadata_requires_variants(self):
        with tempfile.TemporaryDirectory() as tmp:
            sweep_dir = Path(tmp)
            (sweep_dir / "metadata.json").write_text(json.dumps({"render_config": {}}))

            with self.assertRaisesRegex(ValueError, "variants"):
                load_sweep_metadata(sweep_dir)

    def test_import_recipe_callable_uses_module_colon_name(self):
        sqrt = import_recipe_callable("math:sqrt")

        self.assertEqual(sqrt(9), 3)
        with self.assertRaisesRegex(ValueError, "module:callable"):
            import_recipe_callable("math.sqrt")

    def test_safe_variant_name_is_path_friendly(self):
        self.assertEqual(safe_variant_name("wide shell/hero"), "wide_shell_hero")
        self.assertEqual(safe_variant_name("..."), "pick")

    def test_promote_from_metadata_defaults_to_review_winner(self):
        calls = []
        original_render_selected_variant = promote_module.render_selected_variant

        def fake_render_selected_variant(**kwargs):
            calls.append(kwargs)
            selected = next(variant for variant in kwargs["variants"] if variant.name == kwargs["pick"])
            return RenderResult(
                name=selected.name,
                raw=None,
                finished=None,
                settings=selected.settings,
                render_skipped=True,
            )

        with tempfile.TemporaryDirectory() as tmp:
            sweep_dir = Path(tmp)
            (sweep_dir / "metadata.json").write_text(
                json.dumps(
                    {
                        "workflow": {"pick_handles": [{"name": "soft_fill", "promotion_command": "blender -- --pick soft_fill"}]},
                        "variants": [
                            {"name": "wide_shell", "settings": {"width": 1.4}},
                            {"name": "soft_fill", "settings": {"fill": 0.8}},
                        ],
                    }
                )
            )
            write_review_log(sweep_dir, winner="soft_fill")
            promote_module.render_selected_variant = fake_render_selected_variant
            try:
                result = promote_from_metadata(
                    sweep_dir=sweep_dir,
                    build_scene=lambda _settings: None,
                    postprocess=None,
                )
            finally:
                promote_module.render_selected_variant = original_render_selected_variant

        self.assertEqual(result.name, "soft_fill")
        self.assertEqual(calls[0]["pick"], "soft_fill")


if __name__ == "__main__":
    unittest.main()
