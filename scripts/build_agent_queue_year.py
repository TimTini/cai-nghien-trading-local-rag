#!/usr/bin/env python3
"""Build agent_direct_queue.json for videos in a published year."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cai_nghien_assistant.config import load_project_config
from cai_nghien_assistant.paths import configure_local_environment
from cai_nghien_assistant.youtube_collect import catalog_entries_filtered

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--content-type", default="regular+livestream")
    args = parser.parse_args()

    root = args.root.resolve()
    configure_local_environment(root)
    config = load_project_config(root)
    entries = catalog_entries_filtered(root, content_type=args.content_type, published_year=args.year)
    queue = [
        {
            "video_id": entry["video_id"],
            "title": entry.get("title", ""),
            "published_at": entry.get("published_at", ""),
            "content_type": entry.get("content_type", ""),
        }
        for entry in entries
    ]
    out = root / config["storage"]["analysis_dir"] / "state" / "agent_direct_queue.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(queue)} videos to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
