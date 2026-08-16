#!/usr/bin/env python3
"""Build agent-direct edits for wnnhFD6f4gA from raw segments only (no VTT)."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIDEO_ID = "wnnhFD6f4gA"
RAW_DIR = ROOT / "data" / "analysis" / "transcript_quality" / VIDEO_ID

FILLER_RE = re.compile(r"^(ừ|ừ ừ|ừ\.)$", re.I)


def dedupe_consecutive_phrases(text: str) -> str:
    words = text.split()
    if len(words) < 4:
        return text

    out: list[str] = []
    i = 0
    while i < len(words):
        best_len = 1
        max_try = min(40, (len(words) - i) // 2)
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
                break
        else:
            out.append(words[i])
            i += 1
    return " ".join(out)


def dedupe_consecutive_words(text: str) -> str:
    return re.sub(r"\b(\w+)(\s+\1\b)+", r"\1", text, flags=re.I)


def apply_conservative_fixes(text: str) -> tuple[str, list[dict]]:
    fixes: list[dict] = []
    t = text

    replacements = [
        (r"\bđầu tư món\b", "đầu tư coin", "asr_term", "ASR: món → coin (ngữ cảnh crypto)", "medium", True),
        (r"\bfuture\b", "futures", "asr_term", "ASR: future → futures", "high", True),
        (r"\b3 lít\b", "3 tỷ", "asr_term", "ASR: lít → tỷ (vay ngân hàng)", "high", False),
        (r"\bVát\b", "Vay", "asr_term", "ASR: Vát → Vay", "high", False),
        (r"\blàm vát\b", "vay", "asr_term", "ASR: vát → vay", "high", False),
        (r"\bdụng dấu muống\b", "đứng tên mượn", "asr_term", "ASR: dụng dấu muống → đứng tên mượn (đất)", "medium", False),
        (r"\bdụng dấu\b", "đứng tên", "asr_term", "ASR: dụng dấu → đứng tên (sổ đất)", "medium", False),
        (r"\bgiả anh kênh lên 80 triệu\b", "giá lên 80 triệu", "asr_term", "ASR: giả anh kênh → giá (mua đất)", "medium", False),
        (r"\bngười giả anh kênh\b", "người giá", "asr_term", "ASR: giả anh kênh → giá", "medium", False),
        (r"\banh kênh lên 80 triệu\b", "giá lên 80 triệu", "asr_term", "ASR: anh kênh → giá", "medium", False),
        (r"\bsổ đứng tiên\b", "sổ đỏ đứng tên", "asr_term", "ASR: đứng tiên → đỏ đứng tên", "low", False),
        (r"\bđồ đất\b", "đất", "asr_term", "ASR: đồ đất → đất", "high", False),
        (r"\bthành danh tỏi\b", "thành danh", "asr_term", "ASR: tỏi → (câu thành danh)", "low", False),
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

    t2 = dedupe_consecutive_words(t)
    if t2 != t:
        fixes.append(
            {
                "change_type": "asr_stutter",
                "confidence": "high",
                "reason": "ASR lặp từ liên tiếp trong cùng segment",
                "trading_term_flag": False,
                "needs_relisten": False,
            }
        )
        t = t2

    t3 = dedupe_consecutive_phrases(t)
    if t3 != t:
        fixes.append(
            {
                "change_type": "asr_stutter",
                "confidence": "high",
                "reason": "ASR lặp cụm từ liên tiếp trong cùng segment",
                "trading_term_flag": False,
                "needs_relisten": False,
            }
        )
        t = t3

    return t, fixes


def is_filler_only(text: str) -> bool:
    t = text.strip()
    if not t:
        return True
    if FILLER_RE.match(t):
        return True
    if t in {"ừ", "ừ ừ"}:
        return True
    return False


def main() -> None:
    meta_path = RAW_DIR / "raw.meta.json"
    with meta_path.open(encoding="utf-8") as f:
        raw_meta = json.load(f)
    raw_file = RAW_DIR / raw_meta["raw_file"]
    segments = []
    with raw_file.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                segments.append(json.loads(line))

    edits: dict[str, dict] = {}
    suspicious_ids: list[str] = []

    for seg in segments:
        idx = seg["segment_index"]
        raw_text = seg["text"]

        if is_filler_only(raw_text):
            if raw_text.strip():
                edit = {
                    "ai_text": "",
                    "change_type": "asr_hallucination",
                    "confidence": "high",
                    "reason": "Whisper tách lặp âm đệm 'ừ' thành nhiều segment ngắn; gộp/bỏ (raw-only)",
                    "needs_relisten": False,
                    "suspicious": False,
                    "trading_term_flag": False,
                }
                edits[str(idx)] = edit
            continue

        fixed, fix_meta = apply_conservative_fixes(raw_text)
        if fixed == raw_text:
            continue

        confs = [f["confidence"] for f in fix_meta] if fix_meta else []
        confidence = "high"
        if "low" in confs:
            confidence = "low"
        elif "medium" in confs:
            confidence = "medium"

        edit: dict = {
            "ai_text": fixed,
            "change_type": fix_meta[0]["change_type"] if fix_meta else "asr_term",
            "confidence": confidence,
            "reason": "Sửa ASR conservative trên raw",
            "needs_relisten": any(f.get("needs_relisten") for f in fix_meta) or confidence == "low",
            "trading_term_flag": any(f.get("trading_term_flag") for f in fix_meta),
        }
        if fix_meta:
            edit["reason"] += "; " + "; ".join(f["reason"] for f in fix_meta)

        if confidence == "low":
            edit["suspicious"] = True
            suspicious_ids.append(seg["segment_id"])
        elif edit.get("needs_relisten"):
            edit["suspicious"] = True
            suspicious_ids.append(seg["segment_id"])

        edits[str(idx)] = edit

    out = ROOT / "scripts" / f"{VIDEO_ID}_edits.json"
    out.write_text(json.dumps(edits, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "edit_count": len(edits),
                "suspicious_count": len(suspicious_ids),
                "out": str(out),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
