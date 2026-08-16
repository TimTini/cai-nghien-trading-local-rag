#!/usr/bin/env python3
"""Build agent-direct edits for 952hOHNkhrs from raw segments only (no VTT)."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIDEO_ID = "952hOHNkhrs"
RAW_DIR = ROOT / "data/analysis/transcript_quality" / VIDEO_ID
CLEAN_SCRIPT = ROOT / "scripts/agent_direct_clean_video.py"

# (pattern, repl, change_type, reason, confidence, trading, suspicious)
RULES: list[tuple] = [
    (r"\bBinh X\b", "BingX", "brand_fix", "ASR: Binh X → BingX", "high", True, False),
    (r"\bbinh x\b", "BingX", "brand_fix", "ASR: binh x → BingX", "high", True, False),
    (r"\bBINX\b", "BingX", "brand_fix", "ASR: BINX → BingX", "high", True, False),
    (r"\bJ5\b", "TradFi", "asr_term", "ASR: J5 → TradFi (sản phẩm BingX TRADEFI)", "medium", True, True),
    (r"\bERO\b", "EUR", "asr_term", "ASR: ERO → EUR (cặp FX)", "high", True, False),
    (r"\bfuture thôi\b", "futures thôi", "asr_term", "ASR: future → futures", "high", True, False),
    (r"\bgiá rổ\b", "spread", "asr_term", "ASR: giá rổ → spread (phí/giá chênh)", "medium", True, False),
    (r"\bgiớn\b", "giữa", "asr_term", "ASR: giớn → giữa", "high", False, False),
    (r"\bchả nét\b", "cháy hết", "asr_term", "ASR: chả nét → cháy hết (tiền/ví)", "medium", False, False),
    (r"\bGrab\b", "gap", "asr_term", "ASR: Grab → gap (gap cuối tuần)", "high", True, False),
    (r"\bZai Tram\b", "Trump", "asr_term", "ASR: Zai Tram → Trump (tweet cuối tuần)", "medium", False, True),
    (r"\btrao đao\b", "dao động", "asr_term", "ASR: trao đao → dao động (thị trường)", "high", False, False),
    (r"\bsupport dầu\b", "hedge dầu", "asr_term", "ASR: support dầu → hedge dầu (ngữ cảnh phòng giá)", "medium", True, True),
    (r"\bsàn DEX\b", "sàn CEX", "asr_term", "ASR: DEX → CEX (BingX là sàn tập trung)", "medium", True, True),
    (r"\btích thì\b", "tích trữ thì", "asr_term", "ASR: tích → tích trữ (xăng)", "high", False, False),
    (r"\btích gì nên\b", "tích trữ gì nên", "asr_term", "ASR: tích gì → tích trữ", "high", False, False),
]


def apply_rules(text: str) -> tuple[str, list[dict], bool]:
    fixes: list[dict] = []
    any_suspicious = False
    t = text
    for pattern, repl, ctype, reason, conf, trading, suspicious in RULES:
        new_t, n = re.subn(pattern, repl, t)
        if n > 0 and new_t != t:
            fixes.append(
                {
                    "change_type": ctype,
                    "confidence": conf,
                    "reason": reason,
                    "trading_term_flag": trading,
                    "needs_relisten": conf == "low" or suspicious,
                    "suspicious": suspicious,
                }
            )
            if suspicious:
                any_suspicious = True
            t = new_t
    return t, fixes, any_suspicious


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

    # Opening hook repeated ~seg 33-37 — pass-through, flag suspicious (possible ASR loop / reprise)
    reprise_indices = {33, 34, 35, 36, 37}
    opening_snippets = [
        "Mua xăng bây giờ về nhà",
        "Hay là làm một lệnh dầu",
        "Thế thì có vẻ đúng kiểu hợp đồng tương lai",
    ]

    for seg in segments:
        idx = seg["segment_index"]
        raw_text = seg["text"]
        fixed, fix_meta, seg_suspicious = apply_rules(raw_text)

        is_reprise = idx in reprise_indices and any(
            raw_text.startswith(s) or s in raw_text for s in opening_snippets
        )
        if is_reprise:
            seg_suspicious = True
            fix_meta.append(
                {
                    "change_type": "asr_hallucination",
                    "confidence": "low",
                    "reason": "Đoạn lặp gần giống mở đầu video — giữ nguyên raw (pass-through)",
                    "trading_term_flag": False,
                    "needs_relisten": True,
                    "suspicious": True,
                }
            )
            fixed = raw_text

        if fixed != raw_text or (is_reprise and seg_suspicious):
            confs = [f["confidence"] for f in fix_meta] if fix_meta else ["low"]
            conf = "low" if "low" in confs else ("medium" if "medium" in confs else "high")
            edit: dict = {
                "ai_text": fixed,
                "change_type": fix_meta[0]["change_type"] if fix_meta else "asr_term",
                "confidence": conf,
                "reason": "; ".join(f["reason"] for f in fix_meta) if fix_meta else "",
                "needs_relisten": any(f.get("needs_relisten") for f in fix_meta) or conf == "low",
                "trading_term_flag": any(f.get("trading_term_flag") for f in fix_meta),
            }
            if seg_suspicious or is_reprise:
                edit["suspicious"] = True
                suspicious_ids.append(seg["segment_id"])
            if fixed == raw_text and is_reprise:
                edit["change_type"] = "asr_hallucination"
            edits[str(idx)] = edit
        elif seg_suspicious:
            suspicious_ids.append(seg["segment_id"])

    out_edits = ROOT / "scripts" / f"{VIDEO_ID}_edits.json"
    out_edits.write_text(json.dumps(edits, ensure_ascii=False, indent=2), encoding="utf-8")

    proc = subprocess.run(
        [
            sys.executable,
            str(CLEAN_SCRIPT),
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
    meta = json.loads(proc.stdout.strip())
    from collections import Counter

    types = Counter(e.get("change_type", "?") for e in edits.values())
    print(
        json.dumps(
            {
                "video_id": VIDEO_ID,
                "segment_count": meta["segment_count"],
                "change_count": meta["change_count"],
                "suspicious_count": meta["suspicious_count"],
                "edit_segments": len(edits),
                "top_issues": [f"{k}: {v}" for k, v in types.most_common()],
                "meta": meta,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
