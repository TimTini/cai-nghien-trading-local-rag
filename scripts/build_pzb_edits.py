#!/usr/bin/env python3
"""Build agent-direct edits for PzbM4HlIHIk from YouTube vi VTT + raw segments."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cai_nghien_assistant.transcripts import parse_vtt

VIDEO_ID = "PzbM4HlIHIk"
SUBSCRIBE = "Hãy subscribe cho kênh Ghiền Mì Gõ Để không bỏ lỡ những video hấp dẫn"
VTT = ROOT / ".cache" / f"agent_direct_{VIDEO_ID}" / f"{VIDEO_ID}.vi.vtt"
RAW_DIR = ROOT / "data" / "analysis" / "transcript_quality" / VIDEO_ID

NOISE_RE = re.compile(r"\[(?:âm nhạc|nhạc|music|applause|vỗ tay)[^\]]*\]", re.I)
TAG_RE = re.compile(r"<[^>]+>")


def clean_line(text: str) -> str:
    text = TAG_RE.sub("", text)
    text = NOISE_RE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


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
                best_len = n
                i = i + n * reps
                out.extend(chunk)
                break
        if best_len == 1:
            out.append(words[i])
            i += 1
    return " ".join(out)


def segment_text_from_cues(cues: list[tuple[float, float, str]], start: float, end: float) -> str:
    parts: list[str] = []
    prev = ""
    for cs, ce, raw in cues:
        if ce <= start or cs >= end:
            continue
        text = clean_line(raw)
        if not text or text == prev:
            continue
        parts.append(text)
        prev = text
    joined = " ".join(parts)
    return dedupe_consecutive_phrases(joined)


def apply_conservative_fixes(text: str) -> tuple[str, list[dict], list[str]]:
    fixes: list[dict] = []
    notes: list[str] = []
    t = text

    replacements = [
        (r"\bOn Earth\b", "ONUS", "brand_fix", "ASR: On Earth → ONUS (sàn ONUS)", "high", True),
        (r"\bon earth\b", "ONUS", "brand_fix", "ASR: on earth → ONUS", "high", True),
        (r"\bOk X\b", "OKX", "brand_fix", "ASR: Ok X → OKX", "high", True),
        (r"\bok x\b", "OKX", "brand_fix", "ASR: ok x → OKX", "high", True),
        (r"\bChính tỏa\b", "Chứng tỏ", "asr_term", "ASR: Chính tỏa → Chứng tỏ", "high", False),
        (r"\bVẫn tấp\b", "Vẫn thấp", "asr_term", "ASR/phụ đề: tấp → thấp", "high", False),
        (r"\bhai pin sàn\b", "hai Pi sàn", "asr_term", "ASR: pin → Pi (token)", "high", True),
        (r"\bPig thật\b", "Pi thật", "asr_term", "ASR: Pig → Pi", "high", True),
        (r"\bGiác của sàn\b", "Giá của sàn", "asr_term", "ASR: Giác → Giá", "high", False),
        (r"\bThằng On Earth\b", "Thằng ONUS", "brand_fix", "ASR: On Earth → ONUS", "high", True),
        (r"\bsàn On Earth\b", "sàn ONUS", "brand_fix", "ASR: On Earth → ONUS", "high", True),
        (r"\btrên On Earth\b", "trên ONUS", "brand_fix", "ASR: On Earth → ONUS", "high", True),
        (r"\bMách còn\b", "Binance còn", "asr_term", "Phụ đề: Mách → Binance (ngữ cảnh listing Pi)", "medium", True),
        (r"\blên biết Pi\b", "listing Pi", "asr_term", "Phụ đề: lên biết → listing", "medium", True),
        (r"\bChuyển vào mắt\b", "Chuyển vào ví", "asr_term", "Phụ đề: mắt → ví (chuyển Pi về ví)", "medium", True),
        (r"\bAtat\b", "Gate", "asr_term", "Phụ đề: Atat → Gate (sàn Gate.io)", "low", True),
        (r"\bXóa cái online\b", "Xóa cái ONUS", "asr_term", "Phụ đề: online → ONUS", "medium", True),
        (r"\bd unused\b", "pending", "asr_term", "ASR: d unused → pending (trạng thái chuyển Pi)", "low", True),
        (r"\bshop lại\b", "số Pi lại", "asr_term", "Phụ đề: shop → số Pi", "medium", True),
        (r"\bbiết bài nền\b", "mainnet", "asr_term", "Phụ đề: biết bài nền → mainnet Pi", "medium", True),
        (r"\btrả gì\b", "chả gì", "asr_term", "Phụ đề: trả → chả (biết đâu được chả gì)", "high", False),
        (r"\bcái tẹp khách\b", "cái tệp khách", "asr_term", "Phụ đề: tẹp → tệp (tệp khách mục tiêu)", "medium", False),
        (r"\btẹp khách\b", "tệp khách", "asr_term", "Phụ đề: tẹp → tệp", "medium", False),
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

    uncertain_patterns = [
        (r"\bTôi cao lắm\b", "Tôi cao lắm — phụ đề giữ nguyên, cần nghe lại ngữ cảnh"),
        (r"\b3\.400 Pi\b", "3.400 Pi — phụ đề có '300', cần nghe lại số lượng"),
        (r"\bKhóa tiếp 3 năm\b", "Khóa tiếp 3 năm — ngữ cảnh Pi lock, cần nghe lại"),
        (r"\bPi thủ nạp\b", "Pi thủ nạp — phụ đề 'pi thủ n', cần nghe lại"),
        (r"\bxung đột\b", "xung đột vs phụ đề 'xung đồ' — cần nghe lại"),
        (r"\bbất đoàn kết\b", "bất đoàn kết vs phụ đề 'bất đàn kết' — cần nghe lại"),
    ]
    for pattern, note in uncertain_patterns:
        if re.search(pattern, t, re.I):
            notes.append(note)

    return t, fixes, notes


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

    cues = parse_vtt(VTT)
    cues = [(s, e, clean_line(t)) for s, e, t in cues if clean_line(t)]

    edits: dict[str, dict] = {}
    suspicious_ids: list[str] = []

    for seg in segments:
        idx = seg["segment_index"]
        raw_text = seg["text"]

        if raw_text == SUBSCRIBE:
            ai_text = segment_text_from_cues(cues, seg["start"], seg["end"])
            if not ai_text:
                edit = {
                    "ai_text": "",
                    "change_type": "asr_hallucination",
                    "confidence": "high",
                    "reason": "Whisper lặp subscribe Ghiền Mì Gõ; không có phụ đề YouTube vi trong cửa sổ thời gian",
                    "needs_relisten": True,
                    "suspicious": True,
                    "trading_term_flag": False,
                }
                edits[str(idx)] = edit
                suspicious_ids.append(seg["segment_id"])
                continue

            fixed, fix_meta, notes = apply_conservative_fixes(ai_text)
            edit: dict = {
                "ai_text": fixed,
                "change_type": "asr_hallucination",
                "confidence": "medium",
                "reason": "Whisper lặp câu subscribe Ghiền Mì Gõ; thay bằng phụ đề YouTube vi (dedupe)",
                "needs_relisten": False,
                "trading_term_flag": any(f.get("trading_term_flag") for f in fix_meta),
            }
            if fix_meta:
                edit["reason"] += "; " + "; ".join(f["reason"] for f in fix_meta)
            if notes:
                edit["reason"] += "; " + "; ".join(notes)
                edit["confidence"] = "low"
                edit["needs_relisten"] = True
                edit["suspicious"] = True
                suspicious_ids.append(seg["segment_id"])
            edits[str(idx)] = edit
            continue

        # Content segments: fix only when raw differs from conservative VTT-aligned text
        vtt_text = segment_text_from_cues(cues, seg["start"], seg["end"])
        fixed, fix_meta, notes = apply_conservative_fixes(raw_text)

        # Prefer VTT when it clearly improves garbled ASR (same time window, longer/more cues)
        if vtt_text and vtt_text != raw_text:
            vtt_fixed, vtt_fix_meta, vtt_notes = apply_conservative_fixes(vtt_text)
            # Use VTT-based text when raw is clearly wrong vs VTT for exchange names etc.
            use_vtt = False
            if re.search(r"On Earth|Ok X|Mách|mắt|Atat|online|Pig|Giác|tấp|tỏa|pin sàn|d unused", raw_text, re.I):
                use_vtt = True
            if use_vtt and vtt_fixed != raw_text:
                fixed = vtt_fixed
                fix_meta = fix_meta + vtt_fix_meta
                notes = notes + vtt_notes
                base_reason = "Whisper ASR lệch phụ đề vi; lấy phụ đề (dedupe) + sửa thuật ngữ"
            elif fixed != raw_text:
                base_reason = "Sửa ASR conservative trên raw"
            else:
                continue
        elif fixed == raw_text:
            continue
        else:
            base_reason = "Sửa ASR conservative trên raw"

        edit = {
            "ai_text": fixed,
            "change_type": fix_meta[0]["change_type"] if fix_meta else "asr_term",
            "confidence": "high",
            "reason": base_reason,
            "needs_relisten": False,
            "trading_term_flag": any(f.get("trading_term_flag") for f in fix_meta),
        }
        if fix_meta:
            confs = [f["confidence"] for f in fix_meta]
            if "low" in confs:
                edit["confidence"] = "low"
            elif "medium" in confs:
                edit["confidence"] = "medium"
            edit["reason"] += "; " + "; ".join(f["reason"] for f in fix_meta)
            edit["needs_relisten"] = any(f.get("needs_relisten") for f in fix_meta) or edit["confidence"] == "low"

        if notes:
            edit["reason"] += "; " + "; ".join(notes)
            edit["confidence"] = "low"
            edit["needs_relisten"] = True
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
