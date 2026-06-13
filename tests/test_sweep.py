import json
import contextlib
import io
import shutil
import tempfile
import unittest
from pathlib import Path

import blender_workbench.sweep as sweep_module
from blender_workbench.artifact_fingerprint import render_cache_fingerprint, write_fingerprint_record
from blender_workbench.camera import camera_distance_for_matching_framing, orbit_location
from blender_workbench.postprocess import (
    PostprocessLookSettings,
    coerce_postprocess_look_settings,
    postprocess_look_variants,
    render_postprocess_sweep,
)
from blender_workbench.presets import RENDER_PRESETS, SWEEP_AXES, TILE_PRESETS, one_axis_variants, seed_stride_axis, stride_axis, two_axis_variants
from blender_workbench.primitives import soft_band_alpha_profile
from blender_workbench.recipes.camera_perspective import (
    CameraPerspectiveSettings,
    camera_perspective_variants,
    coerce_camera_perspective_settings,
)
from blender_workbench.recipes.gobo_lighting import GoboLightingSettings, coerce_gobo_settings, gobo_lighting_variants
from blender_workbench.recipes.mesh_light import MeshLightSettings, coerce_mesh_light_settings, mesh_light_variants
from blender_workbench.recipes.rocket_plume import (
    RocketPlumeSettings,
    coerce_rocket_plume_settings,
    rocket_plume_scout_variants,
    rocket_plume_texture_variants,
)
from blender_workbench.recipes.subsurface import SubsurfaceSettings, coerce_subsurface_settings, subsurface_variants
from blender_workbench.recipes.terrain_environment import (
    TerrainEnvironmentSettings,
    coerce_terrain_environment_settings,
    terrain_environment_variants,
)
from blender_workbench.recipes.transparency import TransparencySettings, coerce_transparency_settings, transparency_variants
from blender_workbench.sweep import (
    RenderConfig,
    RenderResult,
    SweepVariant,
    TileSpec,
    grid_variants,
    infer_procedural_controls,
    named_variants,
    normalize_variant_role,
    replicate_variants,
    render_profile_comparison_from_sweep,
    render_selected_replicates,
    select_variant,
    settings_to_jsonable,
    _sweep_workflow_metadata,
    variants_from_sweep_metadata,
    render_selected_variant,
    write_readme,
)


class SweepTests(unittest.TestCase):
    def test_grid_variants_are_row_major(self):
        variants = grid_variants(
            [("r0", {"a": 1}), ("r1", {"a": 2})],
            [("c0", {"b": 10}), ("c1", {"b": 20})],
            base={"base": True},
        )

        self.assertEqual([variant.name for variant in variants], ["r0_c0", "r0_c1", "r1_c0", "r1_c1"])
        self.assertEqual(variants[2].settings, {"base": True, "a": 2, "b": 10})

    def test_settings_to_jsonable_accepts_variant_settings(self):
        variant = SweepVariant("demo", {"alpha": 0.25})
        self.assertEqual(settings_to_jsonable(variant.settings), {"alpha": 0.25})

    def test_presets_offer_tile_and_axis_defaults(self):
        self.assertIn("plume_alpha_strength", SWEEP_AXES)
        self.assertIn("light_source_jitter", SWEEP_AXES)
        self.assertIn("texture_magnitude", SWEEP_AXES)
        self.assertIn("texture_magnitude_stride", SWEEP_AXES)
        self.assertIn("variation_seed", SWEEP_AXES)
        self.assertIn("camera_perspective", SWEEP_AXES)
        self.assertIn("camera_orbit", SWEEP_AXES)
        self.assertIn("transparency_alpha", SWEEP_AXES)
        self.assertIn("micro_grid", TILE_PRESETS)
        self.assertIn("auto_micro_grid", TILE_PRESETS)
        self.assertIn("auto_tiny_grid", TILE_PRESETS)
        self.assertIn("shape_scout", RENDER_PRESETS)
        self.assertGreaterEqual(TILE_PRESETS["micro_grid"].columns, 6)
        self.assertIsNone(TILE_PRESETS["auto_micro_grid"].columns)
        self.assertLessEqual(RENDER_PRESETS["shape_scout"].samples, 1)

    def test_camera_helpers_match_framing_and_orbit(self):
        self.assertEqual(camera_distance_for_matching_framing(90, base_lens_mm=45, base_distance=4), 8)
        location = orbit_location(target=(0, 0, 0), distance=2, yaw_degrees=0, pitch_degrees=0)

        self.assertAlmostEqual(location[0], 0)
        self.assertAlmostEqual(location[1], -2)
        self.assertAlmostEqual(location[2], 0)

    def test_axis_helpers_merge_base_settings(self):
        variants = one_axis_variants(SWEEP_AXES["plume_shape"], base={"fixed_camera": True}, prefix="demo")

        self.assertEqual(len(variants), 3)
        self.assertEqual(variants[0].name, "demo_needle")
        self.assertTrue(variants[0].settings["fixed_camera"])

    def test_two_axis_helpers_create_grid(self):
        variants = two_axis_variants(
            SWEEP_AXES["plume_alpha_strength"],
            SWEEP_AXES["plume_shape"],
            base={"samples": 32},
        )

        self.assertEqual(len(variants), 9)
        self.assertEqual(variants[0].settings["samples"], 32)
        self.assertIn("shell_alpha", variants[0].settings)
        self.assertIn("width", variants[0].settings)

    def test_named_variants_are_lightweight_case_boards(self):
        variants = named_variants(
            {
                "clean": {"texture_magnitude": 0.0},
                "rugged": {"texture_magnitude": 0.7},
            },
            base={"fixed_camera": True},
            prefix="mat",
            roles={"clean": "baseline"},
            tags_by_name={"rugged": ("candidate_texture",)},
        )

        self.assertEqual([variant.name for variant in variants], ["mat_clean", "mat_rugged"])
        self.assertEqual(variants[1].label, "rugged")
        self.assertTrue(variants[1].settings["fixed_camera"])
        self.assertEqual(variants[0].role, "baseline")
        self.assertEqual(variants[1].tags, ("candidate_texture",))

    def test_procedural_control_inference_and_replicates(self):
        base = SweepVariant(
            "marked",
            {"texture_magnitude": 0.45, "variation_seed": 9},
            label="marked",
            tags=("texture",),
            procedural_controls={"texture_offset": 0.2},
        )

        replicates = replicate_variants(base, seeds=(3, 4), phases=(0.1,))

        self.assertEqual([variant.name for variant in replicates], ["marked_seed3_phase0p1", "marked_seed4_phase0p1"])
        self.assertEqual(replicates[0].settings["variation_seed"], 3)
        self.assertEqual(replicates[0].settings["noise_phase"], 0.1)
        self.assertEqual(replicates[0].replicate_of, "marked")
        self.assertEqual(replicates[0].replicate_index, 1)
        self.assertEqual(replicates[0].tags, ("texture", "robustness_replicate"))
        self.assertEqual(replicates[0].procedural_controls["texture_offset"], 0.2)
        self.assertEqual(replicates[0].procedural_controls["variation_seed"], 3)
        self.assertEqual(infer_procedural_controls(replicates[0].settings), {"variation_seed": 3, "noise_phase": 0.1})

    def test_seed_stride_axis_makes_seed_boards(self):
        axis = seed_stride_axis(center=10, stride=5, steps=(-1, 0, 1))

        self.assertEqual([label for label, _ in axis.values], ["seed5", "seed10", "seed15"])
        self.assertEqual([settings["variation_seed"] for _, settings in axis.values], [5, 10, 15])

    def test_variant_role_validation_rejects_unknown_roles(self):
        self.assertEqual(normalize_variant_role(None), "candidate")
        with self.assertRaisesRegex(ValueError, "Unknown variant role"):
            SweepVariant("bad_role", {}, role="surprise")

    def test_select_variant_accepts_index_name_or_label(self):
        variants = [
            SweepVariant("wide_shell", {"width": 1.4}, label="wide"),
            SweepVariant("soft_fill", {"fill": 0.8}, label="soft"),
        ]

        self.assertEqual(select_variant(variants, 1).name, "wide_shell")
        self.assertEqual(select_variant(variants, "2").name, "soft_fill")
        self.assertEqual(select_variant(variants, "wide_shell").settings["width"], 1.4)
        self.assertEqual(select_variant(variants, "soft").name, "soft_fill")

    def test_select_variant_reports_unknown_picks(self):
        variants = [SweepVariant("wide_shell", {"width": 1.4})]

        with self.assertRaisesRegex(ValueError, "Unknown variant"):
            select_variant(variants, "missing")

    def test_variants_from_sweep_metadata_reconstructs_pickable_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            sweep_dir = Path(tmp)
            (sweep_dir / "metadata.json").write_text(
                json.dumps(
                    {
                        "variants": [
                            {
                                "name": "bright_wide",
                                "label": "wide",
                                "note": "promising thumbnail",
                                "role": "aesthetic_extreme",
                                "tags": ["glow_edge", "glow_edge", "hero_candidate"],
                                "replicate_of": "source_tile",
                                "replicate_index": 2,
                                "procedural_controls": {"variation_seed": 3, "noise_phase": 0.2},
                                "settings": {"width": 1.6, "alpha": 0.05},
                            }
                        ]
                    }
                )
            )

            variants = variants_from_sweep_metadata(sweep_dir)

        self.assertEqual(variants[0].name, "bright_wide")
        self.assertEqual(variants[0].label, "wide")
        self.assertEqual(variants[0].note, "promising thumbnail")
        self.assertEqual(variants[0].role, "aesthetic_extreme")
        self.assertEqual(variants[0].tags, ("glow_edge", "hero_candidate"))
        self.assertEqual(variants[0].replicate_of, "source_tile")
        self.assertEqual(variants[0].replicate_index, 2)
        self.assertEqual(variants[0].procedural_controls["variation_seed"], 3)
        self.assertEqual(variants[0].settings["width"], 1.6)
        self.assertEqual(select_variant(variants, "wide").name, "bright_wide")

    def test_readme_and_workflow_metadata_include_roles(self):
        results = [
            RenderResult(
                name="neutral",
                raw="runs/demo/neutral.raw.png",
                finished=None,
                settings={},
                role="baseline",
                procedural_controls={"variation_seed": 0},
            ),
            RenderResult(
                name="wide_shell",
                raw="runs/demo/wide_shell.raw.png",
                finished=None,
                settings={"width": 1.4},
            ),
            RenderResult(
                name="solid_fail",
                raw="runs/demo/solid_fail.raw.png",
                finished=None,
                settings={},
                role="failure_anchor",
                tags=("too_solid",),
            ),
            RenderResult(
                name="overdone",
                raw="runs/demo/overdone.raw.png",
                finished=None,
                settings={},
                role="aesthetic_extreme",
            ),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            write_readme(out_dir, "Demo Sweep", results)
            text = (out_dir / "README.md").read_text()
        workflow = _sweep_workflow_metadata(results, None)

        self.assertIn("role `baseline`", text)
        self.assertIn("procedural `variation_seed=0`", text)
        self.assertIn("role `candidate`", text)
        self.assertIn("role `failure_anchor`, tags `too_solid`", text)
        self.assertIn("role `aesthetic_extreme`", text)
        self.assertEqual(workflow["pick_handles"][2]["role"], "failure_anchor")
        self.assertEqual(workflow["pick_handles"][2]["tags"], ("too_solid",))
        self.assertEqual(workflow["pick_handles"][0]["procedural_controls"], {"variation_seed": 0})

    def test_write_readme_pushes_grid_to_selected_render(self):
        result = RenderResult(
            name="wide_shell",
            raw="runs/demo/wide_shell.raw.png",
            finished=None,
            settings={"width": 1.4},
            note="good silhouette",
        )

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            write_readme(
                out_dir,
                "Demo Sweep",
                [result],
                promotion_command="blender --background --python examples/demo.py -- --pick {pick}",
            )
            text = (out_dir / "README.md").read_text()

        self.assertIn("pick `wide_shell` or `1`", text)
        self.assertIn("Do not stop at the contact sheet", text)
        self.assertIn("render_selected_from_sweep", text)
        self.assertIn("Done when `selected/<pick>/selected.json` exists", text)
        self.assertIn("blender --background --python examples/demo.py -- --pick wide_shell", text)

    def test_sweep_workflow_metadata_marks_grid_incomplete_until_selected_render(self):
        result = RenderResult(
            name="wide_shell",
            raw="runs/demo/wide_shell.raw.png",
            finished=None,
            settings={"width": 1.4},
            label="wide",
        )

        workflow = _sweep_workflow_metadata(
            [result],
            "blender --background --python examples/demo.py -- --pick {pick}",
        )

        self.assertEqual(workflow["status"], "needs_selected_render")
        self.assertEqual(workflow["required_decision"], "choose_the_most_promising_tile_by_visual_inspection")
        self.assertTrue(workflow["selected_render_required_before_scene_promotion"])
        self.assertEqual(workflow["done_when"], "selected/<pick>/selected.json exists for one chosen tile")
        self.assertEqual(workflow["pick_handles"][0]["name"], "wide_shell")
        self.assertEqual(workflow["pick_handles"][0]["role"], "candidate")
        self.assertEqual(workflow["pick_handles"][0]["promotion_command"], "blender --background --python examples/demo.py -- --pick wide_shell")

    def test_sweep_workflow_metadata_can_include_profile_comparison_command(self):
        result = RenderResult(
            name="wide_shell",
            raw="runs/demo/wide_shell.raw.png",
            finished=None,
            settings={"width": 1.4},
        )

        workflow = _sweep_workflow_metadata(
            [result],
            "blender demo.py -- --pick {pick}",
            "blender demo.py -- --pick {pick} --compare-profiles",
        )

        self.assertEqual(workflow["profile_comparison_command_template"], "blender demo.py -- --pick {pick} --compare-profiles")
        self.assertEqual(
            workflow["pick_handles"][0]["profile_comparison_command"],
            "blender demo.py -- --pick wide_shell --compare-profiles",
        )

    def test_render_profile_comparison_from_sweep_records_metadata_without_blender(self):
        calls = []
        original_render_variant = sweep_module._render_variant
        original_write_contact_sheet = sweep_module.write_contact_sheet

        def fake_render_variant(**kwargs):
            calls.append(kwargs)
            suffix = f".{kwargs['file_suffix']}" if kwargs["file_suffix"] else ""
            raw = kwargs["out_dir"] / f"{kwargs['variant'].name}{suffix}.raw.png"
            raw.parent.mkdir(parents=True, exist_ok=True)
            raw.write_text("image")
            return RenderResult(
                name=kwargs["variant"].name,
                raw=str(raw.relative_to(kwargs["root"])),
                finished=None,
                settings=kwargs["variant"].settings,
                label=kwargs["variant"].label,
                note=kwargs["variant"].note,
                role=kwargs["variant"].role,
                tags=kwargs["variant"].tags,
                engine=kwargs["config"].engine,
                camera_name=kwargs["config"].camera_name,
                fingerprint={"schema": 1, "fingerprint": f"{kwargs['variant'].name}-fp"},
            )

        def fake_contact_sheet(_results, _root, out_path, _tile, **_kwargs):
            out_path.write_text("contact")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sweep = root / "examples/output/demo"
            sweep.mkdir(parents=True)
            (sweep / "metadata.json").write_text(
                json.dumps(
                    {
                        "fingerprint": {"schema": 1, "fingerprint": "source123"},
                        "variants": [
                            {
                                "name": "wide_shell",
                                "label": "wide",
                                "settings": {"alpha": 0.35, "width": 1.4},
                            }
                        ],
                    }
                )
            )
            profiles = (
                ("preview", RenderConfig.cycles_preview()),
                ("hero", RenderConfig.hero_check()),
            )
            sweep_module._render_variant = fake_render_variant
            sweep_module.write_contact_sheet = fake_contact_sheet
            try:
                results = render_profile_comparison_from_sweep(
                    sweep_dir=sweep,
                    pick="wide_shell",
                    build_scene=lambda _settings: None,
                    root=root,
                    profiles=profiles,
                    postprocess=None,
                    title="Demo Profile Comparison",
                )
            finally:
                sweep_module._render_variant = original_render_variant
                sweep_module.write_contact_sheet = original_write_contact_sheet

            out_dir = sweep / "profile_comparison" / "wide_shell"
            payload = json.loads((out_dir / "profile_comparison.json").read_text())
            readme = (out_dir / "README.md").read_text()

        self.assertEqual([result.label for result in results], ["preview", "hero"])
        self.assertEqual(calls[0]["variant"].settings, {"alpha": 0.35, "width": 1.4})
        self.assertEqual(payload["pick"], "wide_shell")
        self.assertEqual(payload["source_sweep"], "examples/output/demo")
        self.assertEqual(payload["source_sweep_fingerprint"]["fingerprint"], "source123")
        self.assertEqual(payload["selected"]["name"], "wide_shell")
        self.assertEqual([profile["name"] for profile in payload["profiles"]], ["preview", "hero"])
        self.assertEqual(payload["profiles"][1]["render_config"]["samples"], RenderConfig.hero_check().samples)
        self.assertEqual(payload["profiles"][0]["result"]["raw"], "examples/output/demo/profile_comparison/wide_shell/wide_shell_preview.profile.raw.png")
        self.assertEqual(payload["contact_sheet"], "examples/output/demo/profile_comparison/wide_shell/profile_comparison.png")
        self.assertIn("Transparency or alpha settings are present", "\n".join(payload["warnings"]))
        self.assertIn("Profile drift check", readme)

    def test_selected_render_blocks_failure_anchor_without_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "Refusing to promote"):
                render_selected_variant(
                    variants=[SweepVariant("solid_fail", {"width": 1.4}, role="failure_anchor")],
                    pick="solid_fail",
                    build_scene=lambda _settings: None,
                    out_dir=Path(tmp),
                )

    def test_render_variant_reuses_existing_only_when_fingerprint_matches(self):
        def build_scene(settings):
            raise AssertionError(f"should not build scene for fresh cache: {settings}")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_dir = root / "runs/demo"
            out_dir.mkdir(parents=True)
            raw = out_dir / "wide_shell.raw.png"
            raw.write_text("image")
            variant = SweepVariant("wide_shell", {"width": 1.4})
            config = RenderConfig(reuse_existing=True)
            fingerprint = render_cache_fingerprint(
                root=root,
                variant_name=variant.name,
                variant_settings=variant.settings,
                render_config=settings_to_jsonable(config),
                build_scene=build_scene,
                postprocess=None,
                extra={"render_label": "sweep", "file_suffix": ""},
            )
            write_fingerprint_record(raw.with_suffix(".fingerprint.json"), fingerprint)

            with contextlib.redirect_stdout(io.StringIO()):
                result = sweep_module._render_variant(
                    variant=variant,
                    build_scene=build_scene,
                    out_dir=out_dir,
                    root=root,
                    config=config,
                    postprocess=None,
                )

        self.assertTrue(result.skipped_existing)
        self.assertEqual(result.cache_status, "present_fresh")
        self.assertEqual(result.fingerprint["fingerprint"], fingerprint["fingerprint"])

    def test_selected_blend_export_writes_readme_and_metadata_without_render(self):
        calls = []
        original_render_variant = sweep_module._render_variant

        def fake_render_variant(**kwargs):
            calls.append(kwargs)
            blend_path = kwargs["save_blend_path"]
            return RenderResult(
                name=kwargs["variant"].name,
                raw=None,
                finished=None,
                settings=kwargs["variant"].settings,
                blend=str(blend_path.relative_to(kwargs["root"])),
                open_blend_command=f"open -a Blender {blend_path.relative_to(kwargs['root'])}",
                render_skipped=True,
                engine=kwargs["config"].engine,
                camera_name=kwargs["config"].camera_name,
                build_seconds=0.01,
                render_seconds=0.0,
                postprocess_seconds=0.0,
            )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_dir = root / "examples/output/demo/selected/wide_shell"
            source_sweep = root / "examples/output/demo"
            source_sweep.mkdir(parents=True)
            (source_sweep / "metadata.json").write_text(
                json.dumps(
                    {
                        "fingerprint": {"schema": 1, "fingerprint": "source123"},
                        "title": "Demo Sweep",
                        "workflow": {
                            "pick_handles": [
                                {
                                    "name": "wide_shell",
                                    "promotion_command": "blender --background --python examples/demo.py -- --pick wide_shell",
                                },
                                {"name": "flat_fail", "role": "failure_anchor", "note": "lost the silhouette"},
                            ]
                        },
                    }
                )
            )
            sweep_module._render_variant = fake_render_variant
            try:
                result = render_selected_variant(
                    variants=[SweepVariant("wide_shell", {"width": 1.4}, label="wide")],
                    pick="wide_shell",
                    build_scene=lambda _settings: None,
                    out_dir=out_dir,
                    root=root,
                    config=RenderConfig(camera_name="DemoCamera"),
                    postprocess=None,
                    source_sweep_dir=source_sweep,
                    handoff_notes={
                        "preserve": ["Keep the hard rim legible."],
                        "improve_after": ["Refine surface detail after silhouette works."],
                        "failure_modes": ["Avoid the flat_fail silhouette collapse."],
                        "reference_targets": ["refs/demo.png"],
                    },
                    save_blend=True,
                    render_image=False,
                )
            finally:
                sweep_module._render_variant = original_render_variant

            payload = json.loads((out_dir / "selected.json").read_text())
            prompt_card = json.loads((out_dir / "prompt_card.json").read_text())
            handoff = (out_dir / "handoff.md").read_text()
            readme = (out_dir / "README.md").read_text()

        self.assertEqual(result.blend, "examples/output/demo/selected/wide_shell/wide_shell.blend")
        self.assertFalse(calls[0]["render_image"])
        self.assertEqual(calls[0]["save_blend_path"].name, "wide_shell.blend")
        self.assertTrue(payload["result"]["render_skipped"])
        self.assertIsNone(payload["result"]["raw"])
        self.assertEqual(payload["selected"]["role"], "candidate")
        self.assertIn("fingerprint", payload)
        self.assertEqual(payload["source_sweep_fingerprint"]["fingerprint"], "source123")
        self.assertEqual(payload["blend_export"]["path"], "examples/output/demo/selected/wide_shell/wide_shell.blend")
        self.assertEqual(payload["blend_export"]["camera_name"], "DemoCamera")
        self.assertFalse(payload["blend_export"]["render_image"])
        self.assertEqual(payload["handoff"]["markdown"], "examples/output/demo/selected/wide_shell/handoff.md")
        self.assertEqual(payload["handoff"]["prompt_card"], "examples/output/demo/selected/wide_shell/prompt_card.json")
        self.assertEqual(prompt_card["selected"]["name"], "wide_shell")
        self.assertEqual(prompt_card["source"]["sweep_title"], "Demo Sweep")
        self.assertIn("Keep the hard rim legible.", prompt_card["preserve"])
        self.assertIn("Refine surface detail after silhouette works.", prompt_card["improve_after"])
        self.assertIn("Avoid the flat_fail silhouette collapse.", prompt_card["failure_modes"])
        self.assertEqual(prompt_card["reference_targets"], ["refs/demo.png"])
        self.assertEqual(prompt_card["regenerate_command"], "blender --background --python examples/demo.py -- --pick wide_shell")
        self.assertEqual(prompt_card["rejected_neighboring_tiles"][0]["name"], "flat_fail")
        self.assertIn("No image render was requested", readme)
        self.assertIn("Open for GUI review", readme)
        self.assertIn("Handoff", readme)
        self.assertIn("handoff.md", readme)
        self.assertIn("Use this render or study as a structure reference, not final art", handoff)
        self.assertIn("Keep the hard rim legible", handoff)
        self.assertIn("open -a Blender examples/output/demo/selected/wide_shell/wide_shell.blend", readme)

    def test_selected_replicates_write_metadata_without_blender(self):
        calls = []
        original_render_variant = sweep_module._render_variant

        def fake_render_variant(**kwargs):
            calls.append(kwargs)
            variant = kwargs["variant"]
            blend_path = kwargs["save_blend_path"]
            return RenderResult(
                name=variant.name,
                raw=None,
                finished=None,
                settings=variant.settings,
                label=variant.label,
                note=variant.note,
                role=variant.role,
                tags=variant.tags,
                replicate_of=variant.replicate_of,
                replicate_index=variant.replicate_index,
                procedural_controls=variant.procedural_controls,
                blend=str(blend_path.relative_to(kwargs["root"])),
                open_blend_command=f"open -a Blender {blend_path.relative_to(kwargs['root'])}",
                render_skipped=True,
                engine=kwargs["config"].engine,
                camera_name=kwargs["config"].camera_name,
                build_seconds=0.01,
                render_seconds=0.0,
                postprocess_seconds=0.0,
            )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_dir = root / "examples/output/demo/selected/marked/replicates"
            source_sweep = root / "examples/output/demo"
            source_sweep.mkdir(parents=True)
            sweep_module._render_variant = fake_render_variant
            try:
                results = render_selected_replicates(
                    variants=[SweepVariant("marked", {"texture_magnitude": 0.45, "variation_seed": 0}, label="marked")],
                    pick="marked",
                    build_scene=lambda _settings: None,
                    out_dir=out_dir,
                    root=root,
                    config=RenderConfig(camera_name="DemoCamera"),
                    postprocess=None,
                    source_sweep_dir=source_sweep,
                    seeds=(3, 4),
                    phases=(0.1,),
                    save_blend=True,
                    render_image=False,
                )
            finally:
                sweep_module._render_variant = original_render_variant

            payload = json.loads((out_dir / "replicates.json").read_text())
            readme = (out_dir / "README.md").read_text()

        self.assertEqual(len(results), 2)
        self.assertFalse(calls[0]["render_image"])
        self.assertEqual(payload["workflow"]["stage"], "selected_replicate_check")
        self.assertEqual(payload["workflow"]["status"], "needs_visual_review")
        self.assertIsNone(payload["workflow"]["survived_replicates"])
        self.assertEqual(payload["replicates"][0]["replicate_of"], "marked")
        self.assertEqual(payload["replicates"][0]["procedural_controls"]["variation_seed"], 3)
        self.assertEqual(payload["replicates"][0]["procedural_controls"]["noise_phase"], 0.1)
        self.assertIn("Survived replicate checks: `unknown`", readme)
        self.assertIn("Do not promote a texture/noise-heavy tile solely because one procedural sample looked good.", readme)

    def test_selected_export_requires_an_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "render_image=False requires save_blend=True"):
                render_selected_variant(
                    variants=[SweepVariant("wide_shell", {"width": 1.4})],
                    pick="wide_shell",
                    build_scene=lambda _settings: None,
                    out_dir=Path(tmp),
                    render_image=False,
                )

    def test_tile_spec_auto_columns_make_square_boards(self):
        tile = TileSpec.auto_micro_grid()

        self.assertEqual(TileSpec().width, TileSpec().height)
        self.assertIsNone(TileSpec().columns)
        self.assertEqual(tile.width, tile.height)
        self.assertEqual(tile.columns_for_count(1), 1)
        self.assertEqual(tile.columns_for_count(4), 2)
        self.assertEqual(tile.columns_for_count(9), 3)
        self.assertEqual(tile.columns_for_count(10), 4)

    def test_stride_axis_makes_stride_adjustment_obvious(self):
        axis = stride_axis("demo_stride", "texture_magnitude", center=0.5, stride=0.25, steps=(-2, 0, 2), clamp_min=0.0)

        self.assertEqual([label for label, _ in axis.values], ["m2", "base", "p2"])
        self.assertEqual([settings["texture_magnitude"] for _, settings in axis.values], [0.0, 0.5, 1.0])

    def test_soft_band_alpha_profile_feathers_edges(self):
        profile = soft_band_alpha_profile(0.8, feather_steps=3)

        self.assertEqual(len(profile), 7)
        self.assertEqual(profile, tuple(reversed(profile)))
        self.assertAlmostEqual(profile[3], 0.8)
        self.assertLess(profile[0], profile[1])
        self.assertLess(profile[1], profile[2])

    def test_soft_band_alpha_profile_validates_inputs(self):
        with self.assertRaisesRegex(ValueError, "alpha"):
            soft_band_alpha_profile(1.2)
        with self.assertRaisesRegex(ValueError, "feather_steps"):
            soft_band_alpha_profile(0.5, feather_steps=-1)

    def test_postprocess_look_recipe_exposes_finishing_board(self):
        variants = postprocess_look_variants(prefix="test")
        settings = coerce_postprocess_look_settings({"glow_radius": 12.0, "warmth": -5.0, "unused": True})
        names = [variant.name for variant in variants]

        self.assertEqual(len(variants), 9)
        self.assertIn("test_neutral", names)
        self.assertIn("test_warm_glow", names)
        self.assertIn("test_overdone_fail", names)
        self.assertIsInstance(settings, PostprocessLookSettings)
        self.assertEqual(settings.glow_radius, 12.0)
        self.assertEqual(settings.warmth, -5.0)
        self.assertFalse(hasattr(settings, "unused"))

    def test_render_postprocess_sweep_writes_metadata(self):
        root = Path.cwd()
        source = root / "docs" / "assets" / "mini-plume-sweep.jpg"

        def copy_processor(raw, finished, settings):
            shutil.copyfile(raw, finished)
            return True

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "look_sweep"
            variants = postprocess_look_variants(prefix="test")[:2]
            results = render_postprocess_sweep(
                raw_image=source,
                variants=variants,
                out_dir=out_dir,
                root=root,
                processor=copy_processor,
                title="Test Look Sweep",
            )
            metadata = json.loads((out_dir / "metadata.json").read_text())
            sidecar_exists = (out_dir / "test_neutral.look.fingerprint.json").exists()

        self.assertEqual(len(results), 2)
        self.assertEqual(metadata["mode"], "postprocess_sweep")
        self.assertIn("fingerprint", metadata)
        self.assertIn("fingerprint", metadata["variants"][0])
        self.assertEqual(metadata["variants"][0]["name"], "test_neutral")
        self.assertIn("source_raw", metadata)
        self.assertTrue(sidecar_exists)

    def test_render_config_profiles_are_ordered_by_cost(self):
        self.assertEqual(RenderConfig.shape_scout().engine, "BLENDER_WORKBENCH")
        self.assertEqual(RenderConfig.material_scout().engine, "EEVEE")
        self.assertLess(RenderConfig.shape_scout().resolution_x, RenderConfig.hero_check().resolution_x)
        self.assertLess(RenderConfig.cycles_preview().samples, RenderConfig.hero_check().samples)

    def test_settings_to_jsonable_serializes_render_config(self):
        config = RenderConfig.cycles_preview()
        data = settings_to_jsonable(config)

        self.assertEqual(data["engine"], "CYCLES")
        self.assertEqual(data["transparent_max_bounces"], 18)
        self.assertIn("tile", data)

    def test_rocket_plume_recipe_coerces_known_settings(self):
        settings = coerce_rocket_plume_settings({"width": 1.7, "length": 0.8, "samples": 99})

        self.assertIsInstance(settings, RocketPlumeSettings)
        self.assertEqual(settings.width, 1.7)
        self.assertEqual(settings.length, 0.8)
        self.assertFalse(hasattr(settings, "samples"))

    def test_rocket_plume_scout_is_three_by_three(self):
        variants = rocket_plume_scout_variants(prefix="test")

        self.assertEqual(len(variants), 9)
        self.assertEqual(variants[0].name, "test_ghost_needle")
        self.assertIn("shell_alpha", variants[0].settings)
        self.assertIn("width", variants[0].settings)

    def test_rocket_plume_texture_scout_has_failure_anchor(self):
        variants = rocket_plume_texture_variants(prefix="test")
        names = [variant.name for variant in variants]

        self.assertEqual(len(variants), 16)
        self.assertIn("test_overdone", names)
        self.assertEqual(variants[-1].name, "test_whiteout_fail")
        self.assertEqual(variants[0].role, "baseline")
        self.assertEqual(variants[-1].role, "failure_anchor")
        self.assertEqual(variants[-1].tags, ("whiteout", "too_far"))
        self.assertEqual(next(variant for variant in variants if variant.label == "overdone").role, "aesthetic_extreme")
        self.assertGreater(variants[-1].settings["plume_texture_magnitude"], variants[0].settings["plume_texture_magnitude"])
        self.assertGreater(variants[-1].settings["density_wisp_count"], variants[0].settings["density_wisp_count"])
        self.assertGreater(variants[-1].settings["density_clump_count"], variants[0].settings["density_clump_count"])
        self.assertIn("filament_wiggle", variants[-1].settings)

    def test_gobo_recipe_exposes_dense_lighting_board(self):
        variants = gobo_lighting_variants(prefix="test")
        settings = coerce_gobo_settings({"pattern": "dots", "light_size": 0.4, "unused": True})

        self.assertEqual(len(variants), 16)
        self.assertIsInstance(settings, GoboLightingSettings)
        self.assertEqual(settings.pattern, "dots")
        self.assertEqual(settings.light_size, 0.4)
        self.assertFalse(hasattr(settings, "unused"))

    def test_subsurface_recipe_exposes_dense_material_board(self):
        variants = subsurface_variants(prefix="test")
        settings = coerce_subsurface_settings({"subsurface_weight": 0.5, "core_light_energy": 99, "unused": True})
        names = [variant.name for variant in variants]

        self.assertEqual(len(variants), 16)
        self.assertIn("test_matte_fail", names)
        self.assertIn("test_overdone", names)
        self.assertIsInstance(settings, SubsurfaceSettings)
        self.assertEqual(settings.subsurface_weight, 0.5)
        self.assertEqual(settings.core_light_energy, 99)
        self.assertFalse(hasattr(settings, "unused"))

    def test_mesh_light_recipe_exposes_same_view_lighting_board(self):
        variants = mesh_light_variants(prefix="test")
        settings = coerce_mesh_light_settings({"panel_width": 2.0, "fill_strength": 12.0, "unused": True})
        names = [variant.name for variant in variants]

        self.assertEqual(len(variants), 25)
        self.assertIn("test_size_m2", names)
        self.assertIn("test_dist_p2", names)
        self.assertIn("test_height_base", names)
        self.assertIn("test_fill_p2", names)
        self.assertIn("test_gel_m2", names)
        self.assertIsInstance(settings, MeshLightSettings)
        self.assertEqual(settings.panel_width, 2.0)
        self.assertEqual(settings.fill_strength, 12.0)
        self.assertFalse(hasattr(settings, "unused"))

    def test_terrain_environment_recipe_exposes_landscape_board(self):
        variants = terrain_environment_variants(prefix="test")
        settings = coerce_terrain_environment_settings({"terrain_relief": 0.8, "haze_alpha": 0.4, "unused": True})
        names = [variant.name for variant in variants]

        self.assertEqual(len(variants), 25)
        self.assertIn("test_relief_m2", names)
        self.assertIn("test_strata_p2", names)
        self.assertIn("test_haze_base", names)
        self.assertIn("test_light_p1", names)
        self.assertIn("test_fg_p2", names)
        self.assertIsInstance(settings, TerrainEnvironmentSettings)
        self.assertEqual(settings.terrain_relief, 0.8)
        self.assertEqual(settings.haze_alpha, 0.4)
        self.assertFalse(hasattr(settings, "unused"))

    def test_camera_perspective_recipe_exposes_lens_distance_board(self):
        variants = camera_perspective_variants(prefix="test")
        settings = coerce_camera_perspective_settings({"camera_lens": 24, "subject_y": 0.4, "unused": True})
        names = [variant.name for variant in variants]

        self.assertEqual(len(variants), 25)
        self.assertIn("test_lens_m2", names)
        self.assertIn("test_fg_p2", names)
        self.assertIn("test_bg_p2", names)
        self.assertIn("test_grid_p2", names)
        self.assertIn("test_subj_p2", names)
        self.assertIsInstance(settings, CameraPerspectiveSettings)
        self.assertEqual(settings.camera_lens, 24)
        self.assertEqual(settings.subject_y, 0.4)
        self.assertFalse(hasattr(settings, "unused"))

    def test_camera_perspective_recipe_keeps_same_view_by_default(self):
        variants = camera_perspective_variants(prefix="test")

        self.assertTrue(all(variant.settings["camera_yaw"] == 0 for variant in variants))
        self.assertTrue(all(variant.settings["camera_roll"] == 0 for variant in variants))
        self.assertEqual([variant.label.split("_")[0] for variant in variants[5:10]], ["fg"] * 5)

    def test_camera_perspective_recipe_accepts_stride_adjustment(self):
        timid = camera_perspective_variants(prefix="test", lens_stride=8)
        loud = camera_perspective_variants(prefix="test", lens_stride=40)
        timid_depth = camera_perspective_variants(prefix="test", foreground_stride=0.12)
        loud_depth = camera_perspective_variants(prefix="test", foreground_stride=0.6)

        self.assertLess(timid[0].settings["camera_lens"], timid[2].settings["camera_lens"])
        self.assertLess(loud[0].settings["camera_lens"], timid[0].settings["camera_lens"])
        self.assertGreater(loud[4].settings["camera_distance"], timid[4].settings["camera_distance"])
        self.assertLess(loud_depth[5].settings["foreground_depth"], timid_depth[5].settings["foreground_depth"])
        self.assertGreater(loud_depth[9].settings["foreground_depth"], timid_depth[9].settings["foreground_depth"])

    def test_transparency_recipe_exposes_dense_material_board(self):
        variants = transparency_variants(prefix="test")
        settings = coerce_transparency_settings({"alpha": 0.25, "ior": 1.8, "unused": True})
        names = [variant.name for variant in variants]

        self.assertEqual(len(variants), 25)
        self.assertIn("test_alpha_m2", names)
        self.assertIn("test_ior_p2", names)
        self.assertIn("test_tint_p2", names)
        self.assertIsInstance(settings, TransparencySettings)
        self.assertEqual(settings.alpha, 0.25)
        self.assertEqual(settings.ior, 1.8)
        self.assertFalse(hasattr(settings, "unused"))

    def test_transparency_recipe_accepts_stride_adjustment(self):
        timid = transparency_variants(prefix="test", alpha_stride=0.08, ior_stride=0.12)
        loud = transparency_variants(prefix="test", alpha_stride=0.4, ior_stride=0.55)

        self.assertGreater(timid[0].settings["alpha"], loud[0].settings["alpha"])
        self.assertGreater(timid[10].settings["ior"], loud[10].settings["ior"])
        self.assertGreater(loud[14].settings["ior"], timid[14].settings["ior"])


if __name__ == "__main__":
    unittest.main()
