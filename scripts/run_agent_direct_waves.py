#!/usr/bin/env python3
"""Run agent-direct cleaning waves from coordinator state."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "data" / "analysis" / "state" / "agent_direct_queue.json"
COORD = ROOT / "data" / "analysis" / "state" / "agent_direct_coordinator.json"
BASE = ROOT / "data" / "analysis" / "transcript_quality"
STANDARD = ROOT / "scripts" / "build_agent_direct_standard.py"
UPDATE = ROOT / "scripts" / "agent_direct_update_coordinator.py"
LARGE_THRESHOLD = 400
PARALLEL = 5


def is_done(vid: str) -> bool:
    meta = BASE / vid / "ai_cleaned.meta.json"
    if not meta.exists():
        return False
    with meta.open(encoding="utf-8") as f:
        return json.load(f).get("model_id") == "agent-direct"


def seg_count(vid: str) -> int:
    folder = BASE / vid
    for p in folder.glob("raw_*.jsonl"):
        with p.open(encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())
    return 99999


def pending() -> list[tuple[str, int]]:
    with QUEUE.open(encoding="utf-8") as f:
        queue = json.load(f)
    with COORD.open(encoding="utf-8") as f:
        coord = json.load(f)
    skip = set(coord.get("skip_video_ids", []))
    out: list[tuple[str, int]] = []
    for item in queue:
        vid = item["video_id"]
        if vid in skip or is_done(vid):
            continue
        out.append((vid, seg_count(vid)))
    out.sort(key=lambda x: x[1])
    return out


def next_wave_number() -> int:
    with COORD.open(encoding="utf-8") as f:
        coord = json.load(f)
    waves = coord.get("waves", [])
    if not waves:
        return 1
    return max(w["wave"] for w in waves) + 1


def plan_wave(remaining: list[tuple[str, int]]) -> list[str]:
    if not remaining:
        return []
    vid, segs = remaining[0]
    if segs > LARGE_THRESHOLD:
        return [vid]
    return [v for v, _ in remaining[:PARALLEL]]


def clean_one(vid: str) -> None:
    proc = subprocess.run(
        [sys.executable, str(STANDARD), f"--video-id={vid}", "--hook-loops"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
        raise SystemExit(f"Failed {vid}: {proc.returncode}")
    print(proc.stdout.strip())


def main() -> None:
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--start-wave", type=int, default=None)
    p.add_argument("--max-waves", type=int, default=20)
    args = p.parse_args()

    wave = args.start_wave or next_wave_number()
    for _ in range(args.max_waves):
        rem = pending()
        if not rem:
            print("All done.")
            break
        batch = plan_wave(rem)
        print(f"Wave {wave}: {batch} (segs={[seg_count(v) for v in batch]})")
        for vid in batch:
            clean_one(vid)
        upd = [sys.executable, str(UPDATE), "--wave", str(wave)]
        for vid in batch:
            upd.append(f"--video-id={vid}")
        subprocess.run(upd, cwd=str(ROOT), check=True)
        wave += 1

    rem = pending()
    done = 0
    with QUEUE.open(encoding="utf-8") as f:
        queue = json.load(f)
    with COORD.open(encoding="utf-8") as f:
        skip = set(json.load(f).get("skip_video_ids", []))
    for item in queue:
        if item["video_id"] not in skip and is_done(item["video_id"]):
            done += 1
    print(f"STATUS done={done} remaining={len(rem)}")


if __name__ == "__main__":
    main()
