#!/usr/bin/env python3
"""Approve agent-direct cleaned transcripts (copy ai_cleaned -> approved)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from cai_nghien_assistant.config import load_project_config
from cai_nghien_assistant.paths import configure_local_environment
from cai_nghien_assistant.storage import read_jsonl, write_jsonl
from cai_nghien_assistant.transcript_quality.batch import append_glossary_from_approved
from cai_nghien_assistant.transcript_quality.raw_layer import quality_dir
from cai_nghien_assistant.transcript_quality.review_store import load_review_state, save_review_state
from cai_nghien_assistant.youtube_collect import catalog_entries_filtered

ROOT = Path(__file__).resolve().parents[1]


def is_agent_direct(root: Path, video_id: str) -> bool:
    meta_path = quality_dir(root, video_id) / "ai_cleaned.meta.json"
    if not meta_path.exists():
        return False
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    return str(meta.get("model_id") or "") == "agent-direct"


def approve_one(root: Path, video_id: str) -> dict:
    out_dir = quality_dir(root, video_id)
    ai_path = out_dir / "ai_cleaned.jsonl"
    if not ai_path.exists():
        return {"video_id": video_id, "status": "skipped", "reason": "no_ai_cleaned"}
    if not is_agent_direct(root, video_id):
        return {"video_id": video_id, "status": "skipped", "reason": "not_agent_direct"}

    rows = read_jsonl(ai_path)
    write_jsonl(out_dir / "approved.jsonl", rows, root)
    state = load_review_state(root, video_id)
    if state is None:
        return {"video_id": video_id, "status": "error", "reason": "no_review_state"}
    state.status = "approved"
    state.approved_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    save_review_state(root, state)
    append_glossary_from_approved(root, video_id)
    return {"video_id": video_id, "status": "approved", "segments": len(rows)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--year", type=int, default=None)
    parser.add_argument("--content-type", default="regular+livestream")
    parser.add_argument("--video-id", action="append", default=[])
    args = parser.parse_args()

    root = args.root.resolve()
    configure_local_environment(root)
    if args.video_id:
        video_ids = args.video_id
    else:
        entries = catalog_entries_filtered(
            root,
            content_type=args.content_type,
            published_year=args.year or 2026,
        )
        video_ids = [e["video_id"] for e in entries]

    results = [approve_one(root, vid) for vid in video_ids]
    approved = sum(1 for r in results if r.get("status") == "approved")
    print(json.dumps({"approved": approved, "total": len(video_ids), "results": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
