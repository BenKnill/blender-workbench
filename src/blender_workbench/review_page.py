from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Mapping


def _escape(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _rel_link(target: str | None, *, base: Path, root: Path | None = None) -> str | None:
    if not target:
        return None
    path = Path(target)
    if not path.is_absolute() and root is not None:
        path = root / path
    if not path.is_absolute():
        path = base / path
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_uri()


def _settings_summary(settings: Any) -> str:
    if not isinstance(settings, Mapping):
        return _escape(settings)
    parts = []
    for key, value in list(settings.items())[:6]:
        parts.append(f"{key}={value}")
    if len(settings) > 6:
        parts.append(f"+{len(settings) - 6} more")
    return _escape(", ".join(parts))


def _reviewed_names(review_path: Path) -> set[str]:
    if not review_path.exists():
        return set()
    try:
        payload = json.loads(review_path.read_text())
    except json.JSONDecodeError:
        return set()
    names: set[str] = set()
    for key in ("reviewed", "picks", "rejects"):
        value = payload.get(key) if isinstance(payload, dict) else None
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    names.add(item)
                elif isinstance(item, Mapping) and isinstance(item.get("name"), str):
                    names.add(item["name"])
    entries = payload.get("entries") if isinstance(payload, dict) else None
    if isinstance(entries, list):
        for item in entries:
            if isinstance(item, Mapping) and isinstance(item.get("name"), str):
                names.add(item["name"])
    return names


def _pick_commands(metadata: Mapping[str, Any]) -> dict[str, str]:
    workflow = metadata.get("workflow")
    handles = workflow.get("pick_handles", []) if isinstance(workflow, Mapping) else []
    commands: dict[str, str] = {}
    for handle in handles:
        if not isinstance(handle, Mapping):
            continue
        name = handle.get("name")
        command = handle.get("promotion_command")
        if isinstance(name, str) and isinstance(command, str):
            commands[name] = command
    return commands


def render_review_html(metadata: Mapping[str, Any], *, base: Path, root: Path | None = None) -> str:
    title = metadata.get("title") or "Sweep Review"
    contact_sheet = metadata.get("contact_sheet", {})
    contact_href = _rel_link("contact_sheet.png", base=base, root=None)
    commands = _pick_commands(metadata)
    reviewed = _reviewed_names(base / "review.json")
    variants = metadata.get("variants", [])

    lines = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{_escape(title)}</title>",
        "<style>",
        "body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;margin:0;background:#f7f7f3;color:#20201d}",
        "header{padding:20px 24px;border-bottom:1px solid #d8d6cc;background:#fff}",
        "main{padding:20px 24px}",
        ".contact img{max-width:100%;height:auto;border:1px solid #d8d6cc;background:#111}",
        ".grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:18px;margin-top:22px}",
        ".tile{background:#fff;border:1px solid #d8d6cc;border-radius:6px;padding:12px}",
        ".tile.failure_anchor,.tile.negative_control{border-color:#b64a3a;background:#fff7f4}",
        ".tile.aesthetic_extreme{border-color:#9a7b20;background:#fffbea}",
        ".tile.reviewed{outline:3px solid #4c8fbd}",
        ".media{display:grid;grid-template-columns:1fr;gap:8px}",
        ".media img{max-width:100%;height:auto;border:1px solid #c8c6bc;background:#111}",
        ".meta{font-size:13px;line-height:1.35;color:#46443d}",
        "code,pre{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}",
        "pre{white-space:pre-wrap;background:#f0efe8;padding:8px;border-radius:4px;overflow:auto}",
        ".pill{display:inline-block;border:1px solid #aaa58f;border-radius:999px;padding:1px 7px;margin-right:4px;background:#faf9f2}",
        "button{font:inherit;font-size:12px;padding:4px 8px;border:1px solid #aaa58f;background:#fff;border-radius:4px}",
        "</style>",
        "</head>",
        "<body>",
        "<header>",
        f"<h1>{_escape(title)}</h1>",
        f"<p>{len(variants)} variants. Click any tile image to open it full size.</p>",
        "</header>",
        "<main>",
    ]
    if contact_href and (base / "contact_sheet.png").exists():
        lines.extend(
            [
                '<section class="contact">',
                "<h2>Contact Sheet</h2>",
                f'<a href="{_escape(contact_href)}"><img src="{_escape(contact_href)}" alt="Contact sheet"></a>',
                "</section>",
            ]
        )
    if isinstance(contact_sheet, Mapping):
        tile = contact_sheet.get("tile")
        if tile:
            lines.append(f'<p class="meta">Tile layout: <code>{_escape(json.dumps(tile, sort_keys=True))}</code></p>')
    lines.append('<section class="grid">')
    for index, variant in enumerate(variants, start=1):
        if not isinstance(variant, Mapping):
            continue
        name = variant.get("name") or f"variant_{index}"
        role = variant.get("role") or "candidate"
        classes = ["tile", str(role)]
        if name in reviewed:
            classes.append("reviewed")
        label = variant.get("label")
        note = variant.get("note")
        raw_href = _rel_link(variant.get("raw"), base=base, root=root)
        finished_href = _rel_link(variant.get("finished"), base=base, root=root)
        settings = variant.get("settings", {})
        command = commands.get(str(name))
        lines.append(f'<article class="{_escape(" ".join(classes))}" id="{_escape(name)}">')
        lines.append(f"<h2>{index}. {_escape(name)}</h2>")
        lines.append('<div class="meta">')
        if label and label != name:
            lines.append(f'<span class="pill">label: {_escape(label)}</span>')
        lines.append(f'<span class="pill">role: {_escape(role)}</span>')
        tags = variant.get("tags")
        if isinstance(tags, list):
            for tag in tags:
                lines.append(f'<span class="pill">tag: {_escape(tag)}</span>')
        if note:
            lines.append(f"<p>{_escape(note)}</p>")
        lines.append(f"<p>{_settings_summary(settings)}</p>")
        lines.append("</div>")
        lines.append('<div class="media">')
        for kind, href in (("finished", finished_href), ("raw", raw_href)):
            if href:
                lines.append(
                    f'<a href="{_escape(href)}" title="Open {kind} image full size">'
                    f'<img src="{_escape(href)}" alt="{_escape(name)} {kind} image"></a>'
                )
        lines.append("</div>")
        lines.append("<details><summary>Settings JSON</summary>")
        lines.append(f"<pre>{_escape(json.dumps(settings, indent=2, sort_keys=True))}</pre>")
        lines.append("</details>")
        if command:
            escaped_command = _escape(command)
            lines.append("<details open><summary>Promotion command</summary>")
            lines.append(f"<pre><code>{escaped_command}</code></pre>")
            lines.append(
                f'<button type="button" data-command="{escaped_command}" '
                'onclick="navigator.clipboard.writeText(this.dataset.command)">Copy command</button>'
            )
            lines.append("</details>")
        lines.append("</article>")
    lines.extend(["</section>", "</main>", "</body>", "</html>"])
    return "\n".join(lines)


def write_review_page(
    sweep_dir: Path,
    *,
    root: Path | None = None,
    metadata_path: Path | None = None,
    out_path: Path | None = None,
) -> Path:
    sweep_dir = Path(sweep_dir)
    metadata_path = metadata_path or sweep_dir / "metadata.json"
    out_path = out_path or sweep_dir / "review.html"
    metadata = json.loads(metadata_path.read_text())
    html_text = render_review_html(metadata, base=sweep_dir, root=root or Path.cwd())
    out_path.write_text(html_text)
    return out_path
