#!/usr/bin/env python3
"""Build agent-direct edits for KvddXUkzm7k from raw ASR only (no VTT)."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIDEO_ID = "KvddXUkzm7k"
RAW_DIR = ROOT / "data" / "analysis" / "transcript_quality" / VIDEO_ID


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
        (r"\bsản ngược\b", "xả ngược", "asr_term", "ASR: sản ngược → xả ngược (pullback)", "high", True),
        (r"\blông na\b", "logic này", "asr_term", "ASR: lông na → logic này", "medium", False),
        (r"\bgiật nguyên tục\b", "giật liên tục", "asr_term", "ASR: nguyên tục → liên tục", "high", False),
        (r"\bđua bất động sản\b", "đu đua bất động sản", "asr_term", "ASR: đua → đu đua (BĐS 2021)", "medium", False),
        (r"\btrú chân\b", "trú ẩn", "asr_term", "ASR: trú chân → trú ẩn (safe haven)", "medium", False),
        (r"\bcái lấy này\b", "cái nến này", "asr_term", "ASR: lấy → nến (biểu đồ)", "medium", True),
        (r"\bem gái kia dạy là MA\b", "EMA hay MA", "asr_term", "ASR: em gái kia → EMA/MA (chỉ báo)", "low", True),
        (r"\bcoin mà có thanh khoản\b", "coin nào có thanh khoản", "asr_term", "ASR: coin mà → coin nào", "medium", True),
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
    prev_text = ""

    for seg in segments:
        idx = seg["segment_index"]
        raw_text = seg["text"]
        fixed, fix_meta = apply_fixes(raw_text)

        if raw_text == prev_text and idx > 0:
            edits[str(idx)] = {
                "ai_text": fixed,
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
