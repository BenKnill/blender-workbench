from __future__ import annotations

import dataclasses
import hashlib
import inspect
import json
import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any


FINGERPRINT_SCHEMA = 1
FRESHNESS_MISSING = "missing"
FRESHNESS_FRESH = "present_fresh"
FRESHNESS_STALE = "present_stale"
FRESHNESS_UNVERIFIED = "present_unverified"


def jsonable(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    if isinstance(value, Mapping):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if callable(value):
        return callable_identity(value)
    return value


def stable_json(value: Any) -> str:
    return json.dumps(jsonable(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def stable_sha256(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def callable_identity(func: Callable[..., Any] | None) -> dict[str, Any] | None:
    if func is None:
        return None
    identity: dict[str, Any] = {
        "module": getattr(func, "__module__", None),
        "qualname": getattr(func, "__qualname__", repr(func)),
    }
    try:
        source = inspect.getsource(func)
    except (OSError, TypeError):
        source = None
    if source is not None:
        identity["source_sha256"] = hashlib.sha256(source.encode("utf-8")).hexdigest()
    return identity


def _run(cmd: list[str]) -> tuple[bool, str]:
    try:
        completed = subprocess.run(cmd, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True, completed.stdout.strip() or completed.stderr.strip()
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        return False, detail.strip()


def collect_git_state(root: Path, *, runner: Callable[[list[str]], tuple[bool, str]] = _run) -> dict[str, Any]:
    ok_head, head = runner(["git", "-C", str(root), "rev-parse", "HEAD"])
    ok_status, status = runner(["git", "-C", str(root), "status", "--short"])
    return {
        "commit": head if ok_head else None,
        "dirty": bool(status.strip()) if ok_status else None,
        "status_short": status if ok_status else None,
        "available": ok_head and ok_status,
    }


def make_artifact_fingerprint(kind: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    normalized_payload = {
        "schema": FINGERPRINT_SCHEMA,
        "kind": kind,
        **jsonable(payload),
    }
    return {
        "schema": FINGERPRINT_SCHEMA,
        "kind": kind,
        "fingerprint": stable_sha256(normalized_payload),
        "payload": normalized_payload,
    }


def render_cache_fingerprint(
    *,
    root: Path,
    variant_name: str,
    variant_settings: Any,
    render_config: Any,
    build_scene: Callable[[Any], None],
    postprocess: Callable[..., Any] | None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "workbench_git": collect_git_state(root),
        "variant_name": variant_name,
        "variant_settings": variant_settings,
        "render_config": render_config,
        "build_scene": callable_identity(build_scene),
        "postprocess": callable_identity(postprocess),
        "extra": dict(extra or {}),
    }
    return make_artifact_fingerprint("render_cache", payload)


def fingerprint_sidecar_path(path: Path) -> Path:
    return path.with_suffix(".fingerprint.json")


def write_fingerprint_record(path: Path, record: Mapping[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(jsonable(record), indent=2) + "\n")
    return path


def load_fingerprint_record(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("schema") != FINGERPRINT_SCHEMA or not payload.get("fingerprint"):
        return None
    return payload


def load_artifact_fingerprint(path: Path) -> dict[str, Any] | None:
    sidecar = load_fingerprint_record(fingerprint_sidecar_path(path))
    if sidecar is not None:
        return sidecar
    if path.suffix == ".json" and path.exists():
        try:
            payload = json.loads(path.read_text())
        except json.JSONDecodeError:
            return None
        embedded = payload.get("fingerprint") if isinstance(payload, dict) else None
        if isinstance(embedded, dict) and embedded.get("fingerprint"):
            return embedded
    return None


def fingerprint_status(path: Path, expected_fingerprint: str | None = None) -> str:
    if not path.exists():
        return FRESHNESS_MISSING
    record = load_artifact_fingerprint(path)
    if record is None:
        return FRESHNESS_UNVERIFIED
    if expected_fingerprint is None:
        return FRESHNESS_FRESH
    if record.get("fingerprint") == expected_fingerprint:
        return FRESHNESS_FRESH
    return FRESHNESS_STALE


def fingerprint_matches(path: Path, expected: Mapping[str, Any]) -> bool:
    record = load_artifact_fingerprint(path)
    return bool(record and record.get("fingerprint") == expected.get("fingerprint"))
