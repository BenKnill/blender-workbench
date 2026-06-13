# Source Translation Ledger

Older Blender PDFs are useful as artistic prompts, not as instructions to copy blindly. Before turning a page range into a recipe, target panel, or issue, check `docs/source-translation-ledger.json` and decide whether the old workflow should be used as-is, translated, skipped as obsolete, replaced by an existing workbench helper, or manually checked against the current Blender Manual.

Use the ledger like this:

```bash
python3 tools/reference_manifest.py verify
python3 tools/pdf_triage.py ../reference_materials/artistic_blender_pdfs/blenderart_issue_39_compositing_sep_2012.pdf --first-page 8 --last-page 10
```

Then attach the closest `id` from `docs/source-translation-ledger.json` to the page observation, issue, coverage row, or example notes. If no entry fits, add one before implementing the lesson.

Each ledger entry records:

- source id and file
- page range when known
- old term or workflow
- modern Blender concept
- preferred workbench helper, recipe, example, or issue
- status: `use_as_is`, `translate`, `obsolete`, `replaced_by_helper`, or `needs_manual_check`
- version-sensitive notes and related issues/examples/docs

When in doubt, keep the durable visual lesson and throw away the dated UI path. Current helper code and small sweeps should be the implementation surface; old screenshots are evidence for intent.
