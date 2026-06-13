import tempfile
import unittest
from pathlib import Path

from blender_workbench.handoff import format_handoff_markdown, prompt_card_from_reference_prompt


class HandoffTests(unittest.TestCase):
    def test_reference_use_prompt_maps_to_prompt_card_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            study = root / "fast_distinct_lighting_studies_v2/01_dust_beam_silhouette"
            study.mkdir(parents=True)
            prompt = study / "reference_use_prompt.md"
            prompt.write_text(
                "\n".join(
                    [
                        "Use this fast Blender study as a structure reference, not final art.",
                        "",
                        "Scene: 01_dust_beam_silhouette",
                        "Lighting: Dusty castle silhouette with a single bright low sun blade.",
                        "",
                        "Keep the two fighters and both blunt steel trainers physically distinct.",
                        "Preserve the squared safety tips and small depth separation at the bind.",
                        "Improve clothing and armor detail only after the object positions remain legible.",
                    ]
                )
            )

            card = prompt_card_from_reference_prompt(prompt, root=root, reference_targets=["preview.png"])
            markdown = format_handoff_markdown(card)

        self.assertEqual(card["artifact_type"], "handoff_prompt_card")
        self.assertEqual(card["selected"]["name"], "01_dust_beam_silhouette")
        self.assertEqual(
            card["source"]["reference_prompt"],
            "fast_distinct_lighting_studies_v2/01_dust_beam_silhouette/reference_use_prompt.md",
        )
        self.assertEqual(card["reference_targets"], ["preview.png"])
        self.assertIn("Dusty castle silhouette", card["visual_intent"][0])
        self.assertEqual(len(card["preserve"]), 2)
        self.assertIn("Improve clothing", card["improve_after"][0])
        self.assertIn("Use this render or study as a structure reference, not final art", markdown)
        self.assertIn("preview.png", markdown)


if __name__ == "__main__":
    unittest.main()
