#!/usr/bin/env python3
"""Analyze agent-direct queue and list next wave candidates."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "data" / "analysis" / "state" / "agent_direct_queue.json"
COORD = ROOT / "data" / "analysis" / "state" / "agent_direct_coordinator.json"
BASE = ROOT / "data" / "analysis" / "transcript_quality"


def is_agent_direct(video_id: str) -> bool:
    meta_path = BASE / video_id / "ai_cleaned.meta.json"
    if not meta_path.exists():
        return False
    with meta_path.open(encoding="utf-8") as f:
        return json.load(f).get("model_id") == "agent-direct"


def raw_segment_count(video_id: str) -> int:
    folder = BASE / video_id
    if not folder.is_dir():
        return -1
    for p in folder.glob("raw_*.jsonl"):
        with p.open(encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())
    return -1


def main() -> None:
    with QUEUE.open(encoding="utf-8") as f:
        queue = json.load(f)
    with COORD.open(encoding="utf-8") as f:
        coord = json.load(f)
    skip = set(coord.get("skip_video_ids", []))

    remaining = []
    done = 0
    for item in queue:
        vid = item["video_id"]
        if vid in skip:
            continue
        if is_agent_direct(vid):
            done += 1
        else:
            segs = raw_segment_count(vid)
            remaining.append({"video_id": vid, "segments": segs, "title": item.get("title", "")})

    print(f"agent-direct done: {done}")
    print(f"remaining: {len(remaining)}")
    print("next 20 (queue order, by segment count for planning):")
    for r in remaining[:20]:
        print(f"  {r['video_id']}\t{r['segments']}\t{r['title'][:60]}")
    large = [r for r in remaining if r["segments"] > 400]
    if large:
        print(f"large (>400 segs): {len(large)}")
        for r in large[:10]:
            print(f"  {r['video_id']}\t{r['segments']}")


if __name__ == "__main__":
    main()
