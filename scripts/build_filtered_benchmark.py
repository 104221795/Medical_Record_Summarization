#!/usr/bin/env python3
import json

SKIP = {"multiclinsum_ls_en_10012", "multiclinsum_ls_en_10018"}
IN_PATH = "data/processed/governance/benchmark_set.jsonl"
OUT_PATH = "data/processed/governance/benchmark_set_filtered_50.jsonl"
TARGET = 50

wrote = 0
with open(IN_PATH, "r", encoding="utf-8") as fin, open(OUT_PATH, "w", encoding="utf-8") as fout:
    for line in fin:
        try:
            obj = json.loads(line)
        except Exception:
            continue
        nid = obj.get("note_id")
        if not nid or nid in SKIP:
            continue
        fout.write(json.dumps(obj, ensure_ascii=False) + "\n")
        wrote += 1
        if wrote >= TARGET:
            break

print(f"Wrote {wrote} records to {OUT_PATH}")
