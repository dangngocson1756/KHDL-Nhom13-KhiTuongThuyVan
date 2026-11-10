"""Verify cross-artifact consistency between raw JSON, CSV, JSON, SQLite, HTML dashboard, and Excel workbook."""
from __future__ import annotations
import csv
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from artifact_contract import file_sha256, read_verified_source, validate_core_outputs

def main() -> None:
    raw_records, raw_manifest = read_verified_source(ROOT)
    manifest = validate_core_outputs(ROOT)
    analysis = json.loads((ROOT / "outputs/analysis.json").read_text(encoding="utf-8"))

    with (ROOT / "data/processed/weather_clean.csv").open(encoding="utf-8-sig", newline="") as f:
        clean_csv = list(csv.DictReader(f))
    with (ROOT / "data/processed/weather_rejected.csv").open(encoding="utf-8-sig", newline="") as f:
        rej_csv = list(csv.DictReader(f))
    with (ROOT / "data/processed/row_lineage.csv").open(encoding="utf-8-sig", newline="") as f:
        lin_csv = list(csv.DictReader(f))

    clean_json = json.loads((ROOT / "data/processed/weather_clean.json").read_text(encoding="utf-8"))

    conn = sqlite3.connect((ROOT / "outputs/kttv_weather.sqlite").as_uri() + "?mode=ro", uri=True)
    db_count = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
    conn.close()

    c = analysis["counts"]
    assert len(raw_records) == c["raw_count"] == len(lin_csv), "Lineage total count mismatch!"
    assert c["clean_count"] + c["duplicate_count"] + c["rejected_count"] == c["raw_count"], "Lineage partition sum mismatch!"
    assert len(clean_csv) == len(clean_json) == db_count == c["clean_count"], "Clean record count mismatch across CSV/JSON/SQLite!"
    assert len(rej_csv) == c["rejected_count"], "Rejected count mismatch!"

    for name in ("dashboard", "workbook"):
        meta = json.loads((ROOT / f"outputs/{name}_build.json").read_text(encoding="utf-8"))
        assert meta["core_run_id"] == manifest["run_id"], f"{name} run_id mismatch!"
        assert file_sha256(ROOT / meta["path"]) == meta["sha256"], f"{name} sha256 mismatch!"

    report = {
        "core_run_id": manifest["run_id"],
        "raw_count": c["raw_count"],
        "clean_count": c["clean_count"],
        "duplicate_count": c["duplicate_count"],
        "rejected_count": c["rejected_count"],
        "sqlite_observations": db_count,
        "status": "verified_ok",
    }
    (ROOT / "outputs/DELIVERY_CHECK.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (ROOT / "outputs/AUDIT_RESULTS.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("Delivery check passed:", json.dumps(report))

if __name__ == "__main__":
    main()
