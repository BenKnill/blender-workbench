from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


MANIFEST_SCHEMA = 1


@dataclass(frozen=True)
class ResourceStatus:
    resource_id: str
    resource_type: str
    path: str
    status: str
    detail: str
    expected_size_bytes: int | None = None
    actual_size_bytes: int | None = None
    expected_sha256: str | None = None
    actual_sha256: str | None = None
    expected_file_count: int | None = None
    actual_file_count: int | None = None


def _script_args(argv: list[str] | None = None) -> list[str]:
    values = list(sys.argv[1:] if argv is None else argv)
    if "--" in values:
        return values[values.index("--") + 1 :]
    return values


def default_manifest_path(root: Path | None = None) -> Path:
    root = root or Path.cwd()
    return root / "reference_manifest.json"


def load_manifest(path: Path | None = None, *, root: Path | None = None) -> dict[str, Any]:
    manifest_path = path or default_manifest_path(root)
    payload = json.loads(manifest_path.read_text())
    schema = payload.get("schema")
    if schema != MANIFEST_SCHEMA:
        raise ValueError(f"{manifest_path} schema must be {MANIFEST_SCHEMA}, got {schema!r}")
    resources = payload.get("resources")
    if not isinstance(resources, list):
        raise ValueError(f"{manifest_path} does not contain a resources list")
    return payload


def resolve_resource_path(resource: dict[str, Any], *, root: Path | None = None) -> Path:
    root = root or Path.cwd()
    path = Path(resource["path"])
    return path if path.is_absolute() else (root / path).resolve()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def directory_fingerprint(path: Path) -> tuple[int, int, str]:
    files = sorted(item for item in path.rglob("*") if item.is_file())
    digest = hashlib.sha256()
    total_size = 0
    for item in files:
        rel = item.relative_to(path).as_posix()
        size = item.stat().st_size
        total_size += size
        file_sha = sha256_file(item)
        digest.update(f"{rel}\t{size}\t{file_sha}\n".encode("utf-8"))
    return len(files), total_size, digest.hexdigest()


def verify_resource(resource: dict[str, Any], *, root: Path | None = None) -> ResourceStatus:
    resource_id = resource.get("id", "<missing-id>")
    resource_type = resource.get("type", "unknown")
    path_text = resource.get("path", "")
    if not path_text:
        return ResourceStatus(resource_id, resource_type, path_text, "invalid", "resource is missing path")

    path = resolve_resource_path(resource, root=root)
    if not path.exists():
        return ResourceStatus(
            resource_id,
            resource_type,
            path_text,
            "missing",
            "path does not exist",
            expected_size_bytes=resource.get("size_bytes") or resource.get("total_size_bytes"),
            expected_sha256=resource.get("sha256") or resource.get("aggregate_sha256"),
            expected_file_count=resource.get("file_count"),
        )

    if path.is_dir():
        actual_count, actual_size, actual_digest = directory_fingerprint(path)
        expected_count = resource.get("file_count")
        expected_size = resource.get("total_size_bytes")
        expected_digest = resource.get("aggregate_sha256")
        mismatches: list[str] = []
        if expected_count is not None and actual_count != expected_count:
            mismatches.append(f"file_count expected {expected_count}, got {actual_count}")
        if expected_size is not None and actual_size != expected_size:
            mismatches.append(f"total_size_bytes expected {expected_size}, got {actual_size}")
        if expected_digest and actual_digest != expected_digest:
            mismatches.append("aggregate_sha256 mismatch")
        return ResourceStatus(
            resource_id,
            resource_type,
            path_text,
            "mismatch" if mismatches else "ok",
            "; ".join(mismatches) if mismatches else "directory fingerprint matches",
            expected_size_bytes=expected_size,
            actual_size_bytes=actual_size,
            expected_sha256=expected_digest,
            actual_sha256=actual_digest,
            expected_file_count=expected_count,
            actual_file_count=actual_count,
        )

    actual_size = path.stat().st_size
    actual_digest = sha256_file(path)
    expected_size = resource.get("size_bytes")
    expected_digest = resource.get("sha256")
    mismatches = []
    if expected_size is not None and actual_size != expected_size:
        mismatches.append(f"size_bytes expected {expected_size}, got {actual_size}")
    if expected_digest and actual_digest != expected_digest:
        mismatches.append("sha256 mismatch")
    return ResourceStatus(
        resource_id,
        resource_type,
        path_text,
        "mismatch" if mismatches else "ok",
        "; ".join(mismatches) if mismatches else "file fingerprint matches",
        expected_size_bytes=expected_size,
        actual_size_bytes=actual_size,
        expected_sha256=expected_digest,
        actual_sha256=actual_digest,
    )


def verify_manifest(path: Path | None = None, *, root: Path | None = None) -> list[ResourceStatus]:
    manifest = load_manifest(path, root=root)
    return [verify_resource(resource, root=root) for resource in manifest["resources"]]


def format_status_report(results: list[ResourceStatus]) -> str:
    lines = ["Reference manifest:", ""]
    for result in results:
        lines.append(f"- {result.resource_id}: {result.status}; {result.resource_type}; `{result.path}`")
        lines.append(f"  {result.detail}")
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify and list local reference resources without downloading anything.")
    parser.add_argument("--manifest", type=Path, help="manifest path, default reference_manifest.json")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="repository root used to resolve relative paths")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    subparsers = parser.add_subparsers(dest="command")
    verify_parser = subparsers.add_parser("verify", help="verify every manifest resource")
    verify_parser.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    list_parser = subparsers.add_parser("list", help="list resources without failing on status")
    list_parser.add_argument("--missing", action="store_true", help="only list missing or mismatched resources")
    list_parser.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    return parser.parse_args(_script_args(argv))


def main(argv: list[str] | None = None) -> list[ResourceStatus]:
    args = parse_args(argv)
    command = args.command or "verify"
    results = verify_manifest(args.manifest, root=args.root)
    if command == "list":
        list_missing = getattr(args, "missing", False)
        if list_missing:
            results = [result for result in results if result.status != "ok"]
    if args.json:
        print(json.dumps([asdict(result) for result in results], indent=2))
    else:
        print(format_status_report(results))
    if command == "verify" and any(result.status not in {"ok"} for result in results):
        raise SystemExit(1)
    return results


if __name__ == "__main__":
    main()
