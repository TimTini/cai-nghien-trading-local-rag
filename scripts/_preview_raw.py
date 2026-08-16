#!/usr/bin/env python3
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

for vid in sys.argv[1:]:
    p = Path(f"data/analysis/transcript_quality/{vid}")
    meta = json.load((p / "raw.meta.json").open(encoding="utf-8"))
    segs = [
        json.loads(line)
        for line in (p / meta["raw_file"]).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    print("===", vid, len(segs), "===")
    for s in segs[:8]:
        print(f"[{s['segment_index']}] {s['text'][:140]}")
    print("...")
    for s in segs[-3:]:
        print(f"[{s['segment_index']}] {s['text'][:140]}")
    print()
