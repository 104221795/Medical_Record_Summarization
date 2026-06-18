#!/usr/bin/env python3
import json

IDS = {"multiclinsum_ls_en_10012", "multiclinsum_ls_en_10018"}
IN = "data/processed/governance/benchmark_set.jsonl"
OUT = "data/processed/governance/failed_records_smoke.jsonl"

count = 0
with open(IN, "r", encoding="utf-8") as fin, open(OUT, "w", encoding="utf-8") as fout:
    for line in fin:
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if obj.get("note_id") in IDS:
            fout.write(json.dumps(obj, ensure_ascii=False) + "\n")
            count += 1
print(f"Wrote {count} records to {OUT}")
