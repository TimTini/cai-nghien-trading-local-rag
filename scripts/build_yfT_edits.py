#!/usr/bin/env python3
"""Build agent-direct edits for yfTbuIPBSeE from raw ASR only (no VTT)."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIDEO_ID = "yfTbuIPBSeE"
RAW_DIR = ROOT / "data" / "analysis" / "transcript_quality" / VIDEO_ID
NAY_LOOP = re.compile(r"^Này\.?$", re.I)


def dedupe_consecutive_phrases(text: str) -> str:
    words = text.split()
    if len(words) < 4:
        return text
    out: list[str] = []
    i = 0
    while i < len(words):
        max_try = min(40, (len(words) - i) // 2)
        matched = False
        for n in range(max_try, 0, -1):
            chunk = words[i : i + n]
            reps = 1
            j = i + n
            while j + n <= len(words) and words[j : j + n] == chunk:
                reps += 1
                j += n
            if reps > 1:
                i = i + n * reps
                out.extend(chunk)
                matched = True
                break
        if not matched:
            out.append(words[i])
            i += 1
    return " ".join(out)


def apply_fixes(text: str) -> tuple[str, list[dict]]:
    fixes: list[dict] = []
    t = text

    replacements = [
        (r"\bOKEx\b", "OKX", "brand_fix", "ASR: OKEx → OKX", "high", True),
        (r"\bokex\b", "OKX", "brand_fix", "ASR: okex → OKX", "high", True),
        (r"\bsport\b", "spot", "asr_term", "ASR: sport → spot", "high", True),
        (r"\bSport\b", "Spot", "asr_term", "ASR: Sport → Spot", "high", True),
        (r"\bfuture\b", "futures", "asr_term", "ASR: future → futures", "high", True),
        (r"\bPAM\b", "PUMP", "asr_term", "ASR: PAM → PUMP (token/sự kiện)", "high", True),
        (r"\bnạp dòng\b", "nạp tiền", "asr_term", "ASR: nạp dòng → nạp tiền", "high", True),
        (r"\bTối lượng\b", "Tổng lượng", "asr_term", "ASR: Tối lượng → Tổng lượng", "medium", False),
        (r"\bHưng dẫn\b", "Hướng dẫn", "asr_term", "ASR: Hưng → Hướng", "high", False),
        (r"\bBID hoặc E\b", "BTC hoặc ETH", "asr_term", "ASR: BID/E → BTC/ETH", "medium", True),
        (r"\bchơi sport\b", "chơi spot", "asr_term", "ASR: sport → spot", "high", True),
        (r"\bchưa chơi sport\b", "chưa chơi spot", "asr_term", "ASR: sport → spot", "high", True),
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
                }
            )
            t = new_t

    t2 = dedupe_consecutive_phrases(t)
    if t2 != t:
        fixes.append(
            {
                "change_type": "asr_stutter",
                "confidence": "high",
                "reason": "ASR lặp cụm từ trong cùng segment",
                "trading_term_flag": False,
                "needs_relisten": False,
            }
        )
        t = t2

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

    for seg in segments:
        idx = seg["segment_index"]
        raw_text = seg["text"]

        if NAY_LOOP.match(raw_text.strip()):
            edits[str(idx)] = {
                "ai_text": "",
                "change_type": "asr_hallucination",
                "confidence": "high",
                "reason": "Whisper lặp 'Này' (ASR loop khi thao tác UI); cần nghe lại",
                "needs_relisten": True,
                "suspicious": True,
                "trading_term_flag": False,
            }
            suspicious_ids.append(seg["segment_id"])
            continue

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
            if confidence == "low":
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
