import tempfile
import unittest
from pathlib import Path

from blender_workbench.new_scout import (
    build_scout_plan,
    format_scout_plan,
    scaffold_file_contents,
    scout_slug,
    write_scout_scaffold,
)


class NewScoutTests(unittest.TestCase):
    def test_build_plan_lists_repo_contract_and_manifest_entry(self):
        plan = build_scout_plan(name="caustic water", docs_title="Caustic Water Scout")
        report = format_scout_plan(plan)

        self.assertEqual(plan.slug, "caustic_water")
        self.assertEqual(plan.example_name, "caustic_water_scout")
        self.assertTrue(plan.promotion_applicable)
        self.assertEqual(plan.selected_render_path, "examples/output/caustic_water_scout/selected/<pick>/selected.json")
        self.assertEqual(plan.manifest_entry["script"], "examples/caustic_water_scout.py")
        self.assertEqual(plan.manifest_entry["docs_asset"], "docs/assets/caustic-water-scout.jpg")
        self.assertIn("required", report)
        self.assertIn("--pick selected render required", report)
        self.assertIn("examples/manifest.json", report)
        self.assertIn("docs/assets/caustic-water-scout.jpg", report)

    def test_scaffold_file_contents_include_pick_path(self):
        plan = build_scout_plan(name="caustic_water")
        files = scaffold_file_contents(plan)

        self.assertIn("src/blender_workbench/recipes/caustic_water.py", files)
        self.assertIn("examples/caustic_water_scout.py", files)
        self.assertIn("tests/test_caustic_water.py", files)
        self.assertIn("render_selected_from_sweep", files["examples/caustic_water_scout.py"])
        self.assertIn("--pick", files["examples/caustic_water_scout.py"])
        self.assertIn("failure_anchor", files["src/blender_workbench/recipes/caustic_water.py"])

    def test_write_scaffold_refuses_existing_files_without_force(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = build_scout_plan(name="caustic_water")
            written = write_scout_scaffold(plan, root=root)

            self.assertIn("examples/caustic_water_scout.py", written)
            self.assertTrue((root / "examples/caustic_water_scout.py").exists())
            with self.assertRaisesRegex(FileExistsError, "already exists"):
                write_scout_scaffold(plan, root=root)
            rewritten = write_scout_scaffold(plan, root=root, force=True)
            self.assertEqual(written, rewritten)

    def test_no_pick_plan_marks_promotion_not_applicable(self):
        plan = build_scout_plan(name="static_reference", promotion_applicable=False)
        report = format_scout_plan(plan)

        self.assertFalse(plan.promotion_applicable)
        self.assertIsNone(plan.selected_render_path)
        self.assertIn("not applicable by request", report)
        self.assertIn("not_applicable selected_render", report)

    def test_scout_slug_rejects_empty_names(self):
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            scout_slug("!!!")


if __name__ == "__main__":
    unittest.main()
