#!/usr/bin/env python3
"""Re-clean PzbM4HlIHIk from raw ASR only (was VTT)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIDEO_ID = "PzbM4HlIHIk"
RAW_DIR = ROOT / "data" / "analysis" / "transcript_quality" / VIDEO_ID
SUBSCRIBE = "Hãy subscribe cho kênh Ghiền Mì Gõ Để không bỏ lỡ những video hấp dẫn"
DUPLICATE_LINE = "Mình chuyển thử hai pin sàn On Earth đi thôi"


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
    seen_dup = False

    replacements: list[tuple[str, str, str, bool]] = [
        ("On Earth", "OKX", "ASR: On Earth → OKX (sàn)", False),
        ("tẹp khách", "tệp khách", "ASR: tẹp → tệp", False),
        ("tấp hơn", "thấp hơn", "ASR: tấp → thấp", False),
        ("Chính tỏa", "Chính là", "ASR: tỏa → là", False),
        ("Pig thật", "Pi thật", "ASR: Pig → Pi", False),
        ("hai pin sàn", "hai Pi sàn", "ASR: pin → Pi", False),
        ("Giác của", "Giá của", "ASR: Giác → Giá", False),
        ("Mách còn", "Mainnet còn", "ASR: Mách → Mainnet (chưa chắc)", True),
        ("Atat thì", "ATH thì", "ASR: Atat → ATH", True),
        ("bài nền", "mainnet", "ASR: bài nền → mainnet", True),
    ]

    for seg in segments:
        idx = seg["segment_index"]
        raw_text = seg["text"]

        if raw_text == SUBSCRIBE:
            edits[str(idx)] = {
                "ai_text": "",
                "change_type": "asr_hallucination",
                "confidence": "high",
                "reason": "Whisper hallucination subscribe — cần re-ASR (không dùng VTT)",
                "needs_relisten": True,
                "suspicious": True,
                "trading_term_flag": False,
            }
            suspicious_ids.append(seg["segment_id"])
            continue

        if raw_text == DUPLICATE_LINE:
            if seen_dup:
                edits[str(idx)] = {
                    "ai_text": "",
                    "change_type": "duplicate",
                    "confidence": "high",
                    "reason": "ASR lặp câu giống segment trước",
                    "needs_relisten": False,
                    "suspicious": True,
                    "trading_term_flag": False,
                }
                suspicious_ids.append(seg["segment_id"])
                continue
            seen_dup = True

        fixed = raw_text
        reasons: list[str] = []
        low_conf = False
        for old, new, reason, suspicious in replacements:
            if old in fixed:
                fixed = fixed.replace(old, new)
                reasons.append(reason)
                if suspicious:
                    low_conf = True

        if fixed != raw_text:
            edits[str(idx)] = {
                "ai_text": fixed,
                "change_type": "asr_term",
                "confidence": "low" if low_conf else "high",
                "reason": "; ".join(reasons),
                "needs_relisten": low_conf,
                "suspicious": low_conf,
                "trading_term_flag": "Pi" in fixed or "OKX" in fixed,
            }
            if low_conf:
                suspicious_ids.append(seg["segment_id"])

    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "agent_direct_clean_video.py"),
            "--edits-json",
            json.dumps(edits, ensure_ascii=False),
            "--suspicious-ids",
            json.dumps(list(dict.fromkeys(suspicious_ids)), ensure_ascii=False),
            "--",
            VIDEO_ID,
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
