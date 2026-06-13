from __future__ import annotations

import json
import math
import struct
import zlib
from collections.abc import Iterable
from pathlib import Path
from typing import Any


DIAGNOSTICS_SCHEMA = 1
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _iter_png_chunks(data: bytes):
    offset = len(PNG_SIGNATURE)
    while offset + 8 <= len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        start = offset + 8
        end = start + length
        yield chunk_type, data[start:end]
        offset = end + 4


def _paeth(left: int, up: int, up_left: int) -> int:
    p = left + up - up_left
    pa = abs(p - left)
    pb = abs(p - up)
    pc = abs(p - up_left)
    if pa <= pb and pa <= pc:
        return left
    if pb <= pc:
        return up
    return up_left


def _unfilter_scanlines(raw: bytes, *, width: int, height: int, channels: int) -> list[bytes]:
    row_len = width * channels
    rows: list[bytes] = []
    offset = 0
    previous = bytearray(row_len)
    for _row in range(height):
        filter_type = raw[offset]
        offset += 1
        current = bytearray(raw[offset : offset + row_len])
        offset += row_len
        for index, value in enumerate(current):
            left = current[index - channels] if index >= channels else 0
            up = previous[index]
            up_left = previous[index - channels] if index >= channels else 0
            if filter_type == 1:
                current[index] = (value + left) & 0xFF
            elif filter_type == 2:
                current[index] = (value + up) & 0xFF
            elif filter_type == 3:
                current[index] = (value + ((left + up) // 2)) & 0xFF
            elif filter_type == 4:
                current[index] = (value + _paeth(left, up, up_left)) & 0xFF
            elif filter_type != 0:
                raise ValueError(f"unsupported PNG filter {filter_type}")
        rows.append(bytes(current))
        previous = current
    return rows


def read_png_luma(path: Path) -> tuple[int, int, list[float]]:
    data = Path(path).read_bytes()
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError(f"{path} is not a PNG")
    width = height = bit_depth = color_type = None
    idat = bytearray()
    for chunk_type, payload in _iter_png_chunks(data):
        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type = struct.unpack(">IIBB", payload[:10])
        elif chunk_type == b"IDAT":
            idat.extend(payload)
    if width is None or height is None or bit_depth != 8:
        raise ValueError(f"{path} must be an 8-bit PNG")
    channels_by_type = {0: 1, 2: 3, 4: 2, 6: 4}
    channels = channels_by_type.get(color_type)
    if channels is None:
        raise ValueError(f"{path} uses unsupported PNG color type {color_type}")
    rows = _unfilter_scanlines(zlib.decompress(bytes(idat)), width=width, height=height, channels=channels)
    values: list[float] = []
    for row in rows:
        for index in range(0, len(row), channels):
            if color_type == 0:
                luma = row[index]
            elif color_type == 4:
                luma = row[index]
            else:
                red, green, blue = row[index], row[index + 1], row[index + 2]
                luma = 0.2126 * red + 0.7152 * green + 0.0722 * blue
            values.append(luma / 255.0)
    return width, height, values


def _thumbnail(values: list[float], *, width: int, height: int, size: int = 16) -> list[float]:
    if not values:
        return []
    thumb: list[float] = []
    for y in range(size):
        src_y = min(height - 1, int((y + 0.5) * height / size))
        for x in range(size):
            src_x = min(width - 1, int((x + 0.5) * width / size))
            thumb.append(values[src_y * width + src_x])
    return thumb


def _warnings(brightness: float, contrast: float) -> list[str]:
    warnings: list[str] = []
    if brightness < 0.08:
        warnings.append("too_dark")
    if brightness > 0.92:
        warnings.append("too_bright")
    if contrast < 0.025:
        warnings.append("low_contrast")
    return warnings


def analyze_png(path: Path, *, name: str | None = None) -> dict[str, Any]:
    width, height, values = read_png_luma(path)
    brightness = sum(values) / len(values)
    variance = sum((value - brightness) ** 2 for value in values) / len(values)
    contrast = math.sqrt(variance)
    return {
        "name": name or path.stem,
        "path": str(path),
        "width": width,
        "height": height,
        "brightness": round(brightness, 4),
        "contrast": round(contrast, 4),
        "warnings": _warnings(brightness, contrast),
        "_thumbnail": _thumbnail(values, width=width, height=height),
    }


def _rmse(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return math.sqrt(sum((left - right) ** 2 for left, right in zip(a, b)) / len(a))


def analyze_sweep_images(images: Iterable[tuple[str, Path]]) -> dict[str, Any]:
    tiles = []
    for name, path in images:
        try:
            tiles.append(analyze_png(path, name=name))
        except (OSError, ValueError, zlib.error) as error:
            tiles.append({"name": name, "path": str(path), "warnings": ["unreadable_image"], "error": str(error)})
    distances = []
    for left_index, left in enumerate(tiles):
        left_thumb = left.get("_thumbnail")
        if not isinstance(left_thumb, list):
            continue
        for right in tiles[left_index + 1 :]:
            right_thumb = right.get("_thumbnail")
            if isinstance(right_thumb, list):
                distances.append(_rmse(left_thumb, right_thumb))
    pairwise = {
        "count": len(distances),
        "min_rmse": round(min(distances), 4) if distances else None,
        "mean_rmse": round(sum(distances) / len(distances), 4) if distances else None,
        "max_rmse": round(max(distances), 4) if distances else None,
    }
    warnings: list[str] = []
    mean_rmse = pairwise["mean_rmse"]
    max_rmse = pairwise["max_rmse"]
    if isinstance(mean_rmse, float) and isinstance(max_rmse, float) and (mean_rmse < 0.035 or max_rmse < 0.08):
        warnings.append("low_visual_spread")
    unreadable = sum(1 for tile in tiles if any(value in tile.get("warnings", []) for value in ("too_dark", "too_bright", "low_contrast")))
    if tiles and unreadable == len(tiles):
        warnings.append("all_tiles_low_readability")
    elif tiles and unreadable / len(tiles) >= 0.5:
        warnings.append("many_tiles_low_readability")
    clean_tiles = []
    for tile in tiles:
        tile = dict(tile)
        tile.pop("_thumbnail", None)
        clean_tiles.append(tile)
    recommendations = []
    if "low_visual_spread" in warnings:
        recommendations.append("Variants are visually close; consider widening the relevant *_stride or adding stronger anchors.")
    if any(value in warnings for value in ("all_tiles_low_readability", "many_tiles_low_readability")):
        recommendations.append("Several tiles are dark, blown out, or flat; adjust exposure/material anchors before picking a winner.")
    return {
        "schema": DIAGNOSTICS_SCHEMA,
        "tile_count": len(clean_tiles),
        "tiles": clean_tiles,
        "pairwise": pairwise,
        "warnings": warnings,
        "recommendations": recommendations,
        "stance": "Diagnostics steer human review; they do not choose an automatic winner.",
    }


def format_diagnostics_readme(diagnostics: dict[str, Any]) -> list[str]:
    warnings = diagnostics.get("warnings") if isinstance(diagnostics.get("warnings"), list) else []
    recommendations = diagnostics.get("recommendations") if isinstance(diagnostics.get("recommendations"), list) else []
    pairwise = diagnostics.get("pairwise") if isinstance(diagnostics.get("pairwise"), dict) else {}
    lines = ["Board diagnostics:"]
    if warnings:
        lines.append(f"- Warnings: {', '.join(warnings)}")
    else:
        lines.append("- Warnings: none")
    if pairwise.get("mean_rmse") is not None:
        lines.append(f"- Mean tile distance: `{pairwise.get('mean_rmse')}`")
    for recommendation in recommendations:
        lines.append(f"- {recommendation}")
    lines.append("- Diagnostics steer review; they do not choose an automatic winner.")
    return lines


def write_diagnostics(path: Path, diagnostics: dict[str, Any]) -> None:
    path.write_text(json.dumps(diagnostics, indent=2) + "\n")
