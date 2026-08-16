#!/usr/bin/env python3
"""Build agent-direct edits for MTXpw09Qva0 from raw ASR only (no VTT)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIDEO_ID = "MTXpw09Qva0"
RAW_DIR = ROOT / "data" / "analysis" / "transcript_quality" / VIDEO_ID
SUBSCRIBE = "Hãy subscribe cho kênh Ghiền Mì Gõ Để không bỏ lỡ những video hấp dẫn"


def main() -> None:
    meta_path = RAW_DIR / "raw.meta.json"
    with meta_path.open(encoding="utf-8") as f:
        raw_meta = json.load(f)
    raw_file = RAW_DIR / raw_meta["raw_file"]
    segments = [
        json.loads(line)
        for line in raw_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    edits: dict[str, dict] = {}
    suspicious_ids: list[str] = []

    for seg in segments:
        idx = seg["segment_index"]
        raw_text = seg["text"]
        if raw_text != SUBSCRIBE:
            continue

        edits[str(idx)] = {
            "ai_text": "",
            "change_type": "asr_hallucination",
            "confidence": "high",
            "reason": (
                "Whisper hallucination (Ghiền Mì Gõ subscribe) trên toàn bộ audio; "
                "không có nội dung ASR hợp lệ — cần re-ASR hoặc nghe lại (không dùng VTT)"
            ),
            "needs_relisten": True,
            "suspicious": True,
            "trading_term_flag": False,
        }
        suspicious_ids.append(seg["segment_id"])

    edits_json = json.dumps(edits, ensure_ascii=False)
    suspicious_json = json.dumps(suspicious_ids, ensure_ascii=False)

    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "agent_direct_clean_video.py"),
            VIDEO_ID,
            "--edits-json",
            edits_json,
            "--suspicious-ids",
            suspicious_json,
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
        raise SystemExit(proc.returncode)
    print(proc.stdout.strip())
    print(f"edits={len(edits)} suspicious={len(suspicious_ids)}", file=sys.stderr)


if __name__ == "__main__":
    main()
