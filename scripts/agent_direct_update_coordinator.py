#!/usr/bin/env python3
"""Update agent_direct_coordinator.json after a wave completes."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COORD = ROOT / "data" / "analysis" / "state" / "agent_direct_coordinator.json"
BASE = ROOT / "data" / "analysis" / "transcript_quality"


def is_done(vid: str) -> bool:
    meta = BASE / vid / "ai_cleaned.meta.json"
    if not meta.exists():
        return False
    with meta.open(encoding="utf-8") as f:
        return json.load(f).get("model_id") == "agent-direct"


def main() -> None:
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--wave", type=int, required=True)
    p.add_argument("video_ids", nargs="*")
    p.add_argument("--video-id", action="append", dest="video_ids_opt")
    args = p.parse_args()
    video_ids = list(args.video_ids or []) + list(args.video_ids_opt or [])
    if not video_ids:
        p.error("at least one video_id required")

    with COORD.open(encoding="utf-8") as f:
        coord = json.load(f)

    for vid in video_ids:
        if not is_done(vid):
            raise SystemExit(f"Video not agent-direct done: {vid}")

    # Update or add wave entry
    waves = coord.setdefault("waves", [])
    found = False
    for w in waves:
        if w.get("wave") == args.wave:
            w["status"] = "completed"
            w["video_ids"] = video_ids
            w["parallelism"] = len(video_ids)
            found = True
            break
    if not found:
        waves.append(
            {
                "wave": args.wave,
                "status": "completed",
                "video_ids": video_ids,
                "parallelism": len(video_ids),
            }
        )

    completed = set(coord.get("completed_video_ids", []))
    completed.update(video_ids)
    coord["completed_video_ids"] = sorted(
        completed,
        key=lambda v: video_ids.index(v) if v in video_ids else 9999,
    )
    # preserve queue order for completed list - rebuild from queue
    with (ROOT / "data" / "analysis" / "state" / "agent_direct_queue.json").open(
        encoding="utf-8"
    ) as f:
        queue = json.load(f)
    skip = set(coord.get("skip_video_ids", []))
    ordered_done = [
        item["video_id"]
        for item in queue
        if item["video_id"] not in skip and item["video_id"] in completed
    ]
    coord["completed_video_ids"] = ordered_done
    coord["last_completed_video_id"] = video_ids[-1]

    with COORD.open("w", encoding="utf-8") as f:
        json.dump(coord, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"Wave {args.wave} recorded. Total done: {len(ordered_done)}")


if __name__ == "__main__":
    main()
