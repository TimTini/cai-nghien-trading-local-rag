#!/usr/bin/env python3
"""Build agent-direct edits for iFZ625y7h7M from raw ASR only (no VTT)."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIDEO_ID = "iFZ625y7h7M"
RAW_DIR = ROOT / "data" / "analysis" / "transcript_quality" / VIDEO_ID
NHUC_DIEM = "Nhược điểm của con này, vốn sẽ dày hơn là hang bot kia nhé"


def apply_fixes(text: str) -> tuple[str, list[dict]]:
    fixes: list[dict] = []
    t = text

    replacements = [
        (r"\bMón này\b", "Bot này", "asr_term", "ASR: Món → Bot", "high", True),
        (r"\bMón\b", "Bot", "asr_term", "ASR: Món → Bot", "high", True),
        (r"\bbot trọt\b", "bot short", "asr_term", "ASR: trọt → short", "high", True),
        (r"\bđánh trọt\b", "đánh short", "asr_term", "ASR: trọt → short", "high", True),
        (r"\bđánh lo\b", "đánh long", "asr_term", "ASR: lo → long", "high", True),
        (r"\bđánh loan\b", "đánh long", "asr_term", "ASR: loan → long", "high", True),
        (r"\bđánh sọt\b", "đánh short", "asr_term", "ASR: sọt → short", "high", True),
        (r"\bđánh lo hay\b", "đánh long hay", "asr_term", "ASR: lo → long", "high", True),
        (r"\bboss\b", "bot", "asr_term", "ASR: boss → bot", "high", True),
        (r"\bBoss\b", "Bot", "asr_term", "ASR: Boss → Bot", "high", True),
        (r"\bhang bot\b", "bot kia", "asr_term", "ASR: hang bot → bot kia", "medium", True),
        (r"\bFuture\b", "Futures", "asr_term", "ASR: Future → Futures", "high", True),
        (r"\bvinh viết\b", "vĩnh viễn", "asr_term", "ASR: vinh viết → vĩnh viễn", "high", False),
        (r"\bgiả từng đấy\b", "bán từng đấy", "asr_term", "ASR: giả → bán (chốt lệnh grid)", "medium", True),
        (r"\bphải giả từng\b", "phải bán từng", "asr_term", "ASR: giả → bán", "medium", True),
        (r"\bbó nó\b", "bot nó", "asr_term", "ASR: bó → bot", "medium", True),
        (r"\bchạm cái vạch này là đánh trọt\b", "chạm cái vạch này là đánh short", "asr_term", "ASR: trọt → short", "high", True),
        (r"\bchỉ số mạch tương đối\b", "số lưới tương đối", "asr_term", "ASR: mạch → lưới (grid bot)", "low", True),
        (r"\bđến mạng tìm\b", "đếm lưới", "asr_term", "ASR: mạng tìm → đếm lưới", "low", True),
        (r"\báo on\b", "sideway", "asr_term", "ASR: áo on → sideway", "low", True),
        (r"\bcải\b", "cài", "asr_term", "ASR: cải → cài (thông số bot)", "medium", True),
    ]

    for pattern, repl, ctype, reason, conf, trading in replacements:
        new_t, n = re.subn(pattern, repl, t, flags=re.I)
        if n > 0 and new_t != t:
            fixes.append(
                {
                    "change_type": ctype,
                    "confidence": conf,
                    "reason": reason,
                    "trading_term_flag": trading,
                    "needs_relisten": conf == "low",
                    "suspicious": conf == "low",
                }
            )
            t = new_t

    return t, fixes


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
    seen_nhuc = False
    prev_text = ""

    for seg in segments:
        idx = seg["segment_index"]
        raw_text = seg["text"]

        if raw_text == NHUC_DIEM:
            if seen_nhuc:
                edits[str(idx)] = {
                    "ai_text": "",
                    "change_type": "duplicate",
                    "confidence": "high",
                    "reason": "ASR lặp câu 'Nhược điểm...' liên tiếp (Whisper loop)",
                    "needs_relisten": False,
                    "suspicious": True,
                    "trading_term_flag": True,
                }
                suspicious_ids.append(seg["segment_id"])
                continue
            seen_nhuc = True

        if raw_text == prev_text and idx > 0:
            edits[str(idx)] = {
                "ai_text": "",
                "change_type": "duplicate",
                "confidence": "medium",
                "reason": "ASR lặp câu giống segment trước",
                "needs_relisten": False,
                "suspicious": True,
                "trading_term_flag": False,
            }
            suspicious_ids.append(seg["segment_id"])
            prev_text = raw_text
            continue

        prev_text = raw_text
        fixed, fix_meta = apply_fixes(raw_text)

        if fixed != raw_text or fix_meta:
            confs = [f["confidence"] for f in fix_meta]
            confidence = "low" if "low" in confs else ("medium" if "medium" in confs else "high")
            edit: dict = {
                "ai_text": fixed,
                "change_type": fix_meta[0]["change_type"] if fix_meta else "asr_term",
                "confidence": confidence,
                "reason": "; ".join(f["reason"] for f in fix_meta) if fix_meta else "Sửa ASR trên raw",
                "needs_relisten": any(f.get("needs_relisten") for f in fix_meta),
                "trading_term_flag": any(f.get("trading_term_flag") for f in fix_meta),
            }
            if any(f.get("suspicious") for f in fix_meta) or confidence == "low":
                edit["suspicious"] = True
                suspicious_ids.append(seg["segment_id"])
            edits[str(idx)] = edit

    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "agent_direct_clean_video.py"),
            VIDEO_ID,
            "--edits-json",
            json.dumps(edits, ensure_ascii=False),
            "--suspicious-ids",
            json.dumps(suspicious_ids, ensure_ascii=False),
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
