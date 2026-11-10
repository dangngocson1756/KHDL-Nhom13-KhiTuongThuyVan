"""Verify source dataset SHA-256 and output artifact consistency across runs."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read_verified_source(root: Path) -> tuple[list[dict], dict]:
    manifest_path = root / "data/raw/kttv_file_manifest.json"
    if not manifest_path.is_file():
        raise ValueError("Missing raw manifest: data/raw/kttv_file_manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw_path = root / manifest["raw_file"]
    if not raw_path.is_file():
        raise ValueError(f"Missing raw file: {raw_path}")
    actual_sha = file_sha256(raw_path)
    if actual_sha != manifest["sha256"]:
        raise ValueError(f"SHA-256 mismatch on raw file: expected {manifest['sha256']}, got {actual_sha}")
    records = json.loads(raw_path.read_text(encoding="utf-8"))
    if not isinstance(records, list) or len(records) != int(manifest["record_count"]):
        raise ValueError(f"Record count mismatch: expected {manifest['record_count']}, got {len(records)}")
    return records, manifest

def validate_core_outputs(root: Path) -> dict:
    manifest_path = root / "outputs/run_manifest.json"
    if not manifest_path.is_file():
        raise ValueError("Missing outputs/run_manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for rel, expected_hash in manifest.get("artifacts", {}).items():
        target = root / rel
        if not target.is_file():
            raise ValueError(f"Missing artifact from manifest: {rel}")
        actual_hash = file_sha256(target)
        if actual_hash != expected_hash:
            raise ValueError(f"Hash mismatch for {rel}: expected {expected_hash}, got {actual_hash}")
    return manifest
