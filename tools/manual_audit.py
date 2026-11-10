#!/usr/bin/env python3
"""Kiểm tra THỦ CÔNG thật (thay cho bảng "đối chiếu 60 bản ghi" từng bị gõ cứng trong mã).

Quy trình (mù – người kiểm tra KHÔNG thấy quyết định của pipeline):
  1) python tools/manual_audit.py sample            -> docs/audit/manual_audit_sample.csv (+ _pipeline_decisions.csv)
  2) Hai thành viên ĐỘC LẬP điền cột ket_luan_nguoi_kiem_tra bằng một trong: giu | cach_ly | trung
     (dựa trên quy tắc QC đã công bố trong báo cáo, KHÔNG nhìn file quyết định của pipeline).
     Lưu thành manual_audit_labels_A.csv và manual_audit_labels_B.csv trong docs/audit/.
  3) python tools/manual_audit.py score --labels docs/audit/manual_audit_labels_A.csv docs/audit/manual_audit_labels_B.csv
     -> docs/audit/manual_audit_result.json: độ khớp từng người với pipeline, độ khớp giữa hai người (Cohen's kappa).
Chỉ khi chạy đủ 3 bước này mới được ghi "kiểm tra thủ công N bản ghi" vào báo cáo.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "docs/audit"
MAP = {"kept": "giu", "rejected": "cach_ly", "duplicate": "trung"}
RAW_FIELDS = ["temp_mean_raw", "temp_max_raw", "temp_min_raw", "dewpoint_raw", "humidity_raw", "pressure_raw",
              "precip_raw", "wind_speed_raw", "wind_dir_raw", "solar_rad_raw",
              "reanalysis_temp_c", "reanalysis_pressure_hpa"]


def cmd_sample(n: int, seed: int) -> None:
    if n < 30:
        raise ValueError("n must be at least 30 for the stratified sample")
    manifest = json.loads((ROOT / "data/raw/kttv_file_manifest.json").read_text(encoding="utf-8"))
    raw = {int(r["raw_id"]): r for r in json.loads((ROOT / manifest["raw_file"]).read_text(encoding="utf-8"))}
    with (ROOT / "data/processed/row_lineage.csv").open(encoding="utf-8-sig", newline="") as f:
        lineage = {int(r["row_id"]): r for r in csv.DictReader(f)}
    by_status: dict[str, list[int]] = {"rejected": [], "duplicate": [], "kept": []}
    for rid, r in lineage.items():
        by_status[r["status"]].append(rid)
    rng = random.Random(seed)
    take = {s: min(15, len(by_status[s])) for s in ("rejected", "duplicate")}
    take["kept"] = min(len(by_status["kept"]), max(0, n - sum(take.values())))
    chosen = [rid for s, k in take.items() for rid in rng.sample(by_status[s], k)]
    rng.shuffle(chosen)
    AUDIT.mkdir(parents=True, exist_ok=True)
    with (AUDIT / "manual_audit_sample.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["raw_id", "station_code", "obs_date", *RAW_FIELDS, "ket_luan_nguoi_kiem_tra", "ghi_chu"])
        for rid in chosen:
            r = raw[rid]
            w.writerow([rid, r["station_code"], r["obs_date"], *[r.get(k, "") for k in RAW_FIELDS], "", ""])
    # Full context for duplicate checks; strip source_channel and all pipeline labels.
    with (AUDIT / "manual_audit_context.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w=csv.writer(f)
        w.writerow(["raw_id","station_code","obs_date",*RAW_FIELDS])
        for rid,r in sorted(raw.items()):
            w.writerow([rid,r["station_code"],r["obs_date"],*[r.get(k,"") for k in RAW_FIELDS]])
    with (AUDIT / "_pipeline_decisions.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["raw_id", "pipeline_decision", "pipeline_reasons"])
        for rid in chosen:
            w.writerow([rid, MAP[lineage[rid]["status"]], lineage[rid]["reasons"]])
    print(f"Đã tạo mẫu {len(chosen)} bản ghi (seed={seed}): {take}. KHÔNG đưa file _pipeline_decisions.csv cho người kiểm tra.")


def read_labels(path: Path) -> dict[int, str]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        labels={}
        for r in csv.DictReader(f):
            rid=int(r["raw_id"])
            if rid in labels:raise ValueError("Duplicate human-labeled ID")
            labels[rid]=r["ket_luan_nguoi_kiem_tra"].strip().lower()
        return labels


def kappa(a: list[str], b: list[str]) -> float | None:
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return None if pe == 1 else (po - pe) / (1 - pe)


def cmd_score(label_files: list[str]) -> None:
    with (AUDIT / "_pipeline_decisions.csv").open(encoding="utf-8-sig", newline="") as f:
        pipe = {int(r["raw_id"]): r["pipeline_decision"] for r in csv.DictReader(f)}
    result: dict = {"n_sample": len(pipe), "labelers": {}}
    labels = [read_labels(Path(p)) for p in label_files]
    for lab in labels:
        if set(lab) != set(pipe) or any(v not in {"giu", "cach_ly", "trung"} for v in lab.values()):
            raise ValueError("Every sampled ID must have exactly one valid human label; incomplete labels cannot be scored")
    for path, lab in zip(label_files, labels):
        ids = [i for i in pipe if lab.get(i)]
        agree = sum(lab[i] == pipe[i] for i in ids)
        result["labelers"][Path(path).name] = {
            "labeled": len(ids), "agree_with_pipeline": agree,
            "agreement_pct": round(100 * agree / len(ids), 2) if ids else None,
            "confusion": dict(Counter(f"{pipe[i]}->{lab[i]}" for i in ids if lab[i] != pipe[i])),
        }
    if len(labels) == 2:
        ids = [i for i in pipe if labels[0].get(i) and labels[1].get(i)]
        if ids:
            la, lb = [labels[0][i] for i in ids], [labels[1][i] for i in ids]
            result["inter_labeler"] = {"n": len(ids), "agreement_pct": round(100 * sum(x == y for x, y in zip(la, lb)) / len(ids), 2),
                                       "cohen_kappa": (round(kappa(la, lb), 4) if kappa(la, lb) is not None else None)}
    (AUDIT / "manual_audit_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample")
    s.add_argument("--n", type=int, default=60)
    s.add_argument("--seed", type=int, default=20261015)
    sc = sub.add_parser("score")
    sc.add_argument("--labels", nargs="+", required=True)
    args = ap.parse_args()
    cmd_sample(args.n, args.seed) if args.cmd == "sample" else cmd_score(args.labels)
    return 0


if __name__ == "__main__":
    sys.exit(main())
