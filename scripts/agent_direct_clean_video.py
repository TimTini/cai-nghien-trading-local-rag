#!/usr/bin/env python3
"""Write agent-direct cleaned transcript outputs for one video."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

MODEL_ID = "agent-direct"
CLEANER_VERSION = "agent-direct-1.0"
PROMPT_VERSION = "1"
BASE = Path(__file__).resolve().parents[1] / "data" / "analysis" / "transcript_quality"


def load_raw_segments(folder: Path) -> tuple[list[dict], Path, dict]:
    meta_path = folder / "raw.meta.json"
    with meta_path.open(encoding="utf-8") as f:
        raw_meta = json.load(f)
    raw_file = folder / raw_meta["raw_file"]
    segments = []
    with raw_file.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                segments.append(json.loads(line))
    return segments, raw_file, raw_meta


def write_video(
    video_id: str,
    edits: dict[int, dict[str, Any]],
    suspicious_segment_ids: set[str] | None = None,
) -> dict[str, Any]:
    folder = BASE / video_id
    segments, _raw_file, raw_meta = load_raw_segments(folder)
    suspicious_segment_ids = suspicious_segment_ids or set()

    cleaned: list[dict] = []
    changes: list[dict] = []
    suspicious_count = 0

    for seg in segments:
        idx = seg["segment_index"]
        out = dict(seg)
        if idx in edits:
            edit = edits[idx]
            raw_text = seg["text"]
            ai_text = edit.get("ai_text", raw_text)
            out["text"] = ai_text
            if ai_text != raw_text:
                entry = {
                    "ai_text": ai_text,
                    "change_type": edit.get("change_type", "asr_term"),
                    "confidence": edit.get("confidence", "medium"),
                    "end": seg["end"],
                    "needs_relisten": edit.get("needs_relisten", False),
                    "raw_text": raw_text,
                    "reason": edit.get("reason", ""),
                    "segment_id": seg["segment_id"],
                    "segment_index": idx,
                    "start": seg["start"],
                    "trading_term_flag": edit.get("trading_term_flag", False),
                }
                changes.append(entry)
            if edit.get("suspicious"):
                suspicious_count += 1
        cleaned.append(out)

    for sid in suspicious_segment_ids:
        if sid not in {c["segment_id"] for c in changes}:
            suspicious_count += 1

    source_hash = raw_meta["source_hash"]
    title = segments[0].get("title", "") if segments else ""
    published_at = segments[0].get("published_at") if segments else None

    with (folder / "ai_cleaned.jsonl").open("w", encoding="utf-8") as f:
        for row in cleaned:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    with (folder / "change_log.jsonl").open("w", encoding="utf-8") as f:
        for row in changes:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    meta = {
        "video_id": video_id,
        "input_raw_hash": source_hash,
        "raw_source_path": raw_meta["source_path"],
        "cleaner_logic_version": CLEANER_VERSION,
        "cleaner_prompt_version": PROMPT_VERSION,
        "model_id": MODEL_ID,
        "segment_count": len(segments),
        "change_count": len(changes),
        "suspicious_count": suspicious_count,
    }
    with (folder / "ai_cleaned.meta.json").open("w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
        f.write("\n")

    status = "has_suspicious" if suspicious_count else "ai_done_unreviewed"
    review = {
        "video_id": video_id,
        "title": title,
        "published_at": published_at,
        "status": status,
        "model_id": MODEL_ID,
        "cleaner_logic_version": CLEANER_VERSION,
        "raw_source_path": raw_meta["source_path"],
        "raw_source_hash": source_hash,
        "ai_input_hash": source_hash,
        "suspicious_count": suspicious_count,
        "accepted_low_risk": False,
        "approved_at": None,
        "partial_accepted_segment_ids": [],
        "rejected_change_ids": [],
    }
    with (folder / "review_state.json").open("w", encoding="utf-8") as f:
        json.dump(review, f, ensure_ascii=False, indent=2)
        f.write("\n")

    return meta


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--edits-json", default=None)
    parser.add_argument("--edits-file", default=None)
    parser.add_argument("--suspicious-ids", default=None)
    parser.add_argument("--suspicious-file", default=None)
    parser.add_argument("video_id", nargs="?", default=None)
    parser.add_argument("--video-id", dest="video_id_opt")
    args = parser.parse_args()
    video_id = args.video_id or args.video_id_opt
    if not video_id:
        parser.error("video_id required")

    if args.edits_file:
        edits_raw = json.loads(Path(args.edits_file).read_text(encoding="utf-8"))
    else:
        edits_raw = json.loads(args.edits_json or "{}")
    if args.suspicious_file:
        suspicious = set(json.loads(Path(args.suspicious_file).read_text(encoding="utf-8")))
    else:
        suspicious = set(json.loads(args.suspicious_ids or "[]"))

    edits = {int(k): v for k, v in edits_raw.items()}
    meta = write_video(video_id, edits, suspicious)
    print(json.dumps(meta, ensure_ascii=False))


if __name__ == "__main__":
    main()
