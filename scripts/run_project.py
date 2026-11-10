"""Reproduce core artifacts, HTML dashboard, optional Excel workbook, SQL demo, and unit tests."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from artifact_contract import file_sha256, validate_core_outputs

def execute(script: Path, *args: str) -> None:
    subprocess.run([sys.executable, "-X", "utf8", str(ROOT / script), *args], cwd=ROOT, check=True)

def run_tests() -> None:
    manifest = validate_core_outputs(ROOT)
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    record = {
        "core_run_id": manifest["run_id"],
        "status": "passed" if result.wasSuccessful() else "failed",
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "test_files": {p.relative_to(ROOT).as_posix(): file_sha256(p) for p in sorted((ROOT / "tests").glob("test_*.py"))},
    }
    (ROOT / "outputs/python_test_results.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    if not result.wasSuccessful():
        raise ValueError("Python unit tests failed!")

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-download", action="store_true", help="Verify local raw file without re-downloading.")
    parser.add_argument("--workbook", action="store_true", help="Rebuild 3-sheet Excel workbook.")
    parser.add_argument("--skip-tests", action="store_true", help="Skip running unit test suite.")
    args = parser.parse_args()

    if not args.skip_download:
        execute(Path("scripts/download_data.py"))
    execute(Path("scripts/hydrology.py"))
    execute(Path("scripts/real_weather.py"))
    execute(Path("src/pipeline.py"))
    execute(Path("tools/build_dashboard.py"))
    if args.workbook:
        execute(Path("tools/build_workbook.py"))
    execute(Path("tools/report_evidence.py"))
    if not args.skip_tests:
        run_tests()
    execute(Path("scripts/demo_sql.py"))
    execute(Path("tools/verify_delivery.py"))
    execute(Path("tools/prepare_report_sources.py"))
    print("Full project pipeline and verification completed successfully.")

if __name__ == "__main__":
    main()
