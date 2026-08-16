#!/usr/bin/env python3
"""Build agent-direct edits for wc7gJqOE25A from raw ASR only (no VTT)."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIDEO_ID = "wc7gJqOE25A"
RAW_DIR = ROOT / "data" / "analysis" / "transcript_quality" / VIDEO_ID


def apply_fixes(text: str) -> tuple[str, list[dict]]:
    fixes: list[dict] = []
    t = text

    replacements: list[tuple[str, str, str, str, str, bool, bool]] = [
        (r"\bô cỡ x\b", "OKX", "brand_fix", "ASR: ô cỡ x → OKX", "high", True, False),
        (r"\bOKEx\b", "OKX", "brand_fix", "ASR: OKEx → OKX", "high", True, False),
        (r"\bokex\b", "OKX", "brand_fix", "ASR: okex → OKX", "high", True, False),
        (r"\bphiêu dịch\b", "giao dịch", "asr_term", "ASR: phiêu dịch → giao dịch", "high", True, False),
        (r"\bphi gas\b", "phí gas", "asr_term", "ASR: phi gas → phí gas", "high", True, False),
        (r"\bStacking\b", "Staking", "asr_term", "ASR: Stacking → Staking", "high", True, False),
        (r"\bABtrum\b", "Arbitrum", "asr_term", "ASR: ABtrum → Arbitrum", "high", True, False),
        (r"\bDias\b", "dApps", "asr_term", "ASR: Dias → dApps", "high", True, False),
        (r"\bcơ sở hải tầng\b", "cơ sở hạ tầng", "asr_term", "ASR: hải tầng → hạ tầng", "high", False, False),
        (r"\bDark Chain\b", "DuckChain", "asr_term", "ASR: Dark Chain → DuckChain", "high", True, False),
        (r"\bDark\b", "DUCK", "asr_term", "ASR: Dark → DUCK (token)", "high", True, False),
        (r"\bDAX\b", "DUCK", "asr_term", "ASR: DAX → DUCK (token gas)", "high", True, False),
        (r"\bfuture\b", "futures", "asr_term", "ASR: future → futures", "medium", True, False),
        (r"\bDuckTrain\b", "DuckChain", "asr_term", "ASR: DuckTrain → DuckChain", "medium", True, True),
        (r"\btôn\b", "TON", "asr_term", "ASR: tôn → TON (blockchain)", "high", True, False),
        (r"\bDuck\b", "DUCK", "asr_term", "ASR: Duck → DUCK (token)", "high", True, False),
        (r"\bđồng coi\b", "đồng coin", "asr_term", "ASR: coi → coin", "high", True, False),
    ]

    # Opening line: Whisper often hears "Ở" instead of "Trong"
    if t.startswith("Ở hai ngày"):
        new_t = "Trong hai ngày" + t[len("Ở hai ngày") :]
        if new_t != t:
            fixes.append(
                {
                    "change_type": "asr_term",
                    "confidence": "medium",
                    "reason": "ASR: Ở hai ngày → Trong hai ngày",
                    "trading_term_flag": False,
                    "needs_relisten": False,
                }
            )
            t = new_t

    if "Người tiêu dùng EVM đầu tiên trên TON" in t or "Người tiêu dùng EVM" in t:
        new_t = t.replace("Người tiêu dùng EVM", "Nền tảng EVM")
        if new_t != t:
            fixes.append(
                {
                    "change_type": "asr_term",
                    "confidence": "medium",
                    "reason": "ASR: Người tiêu dùng → Nền tảng (EVM on TON)",
                    "trading_term_flag": True,
                    "needs_relisten": False,
                }
            )
            t = new_t

    if t == "Đặc truyền.":
        fixes.append(
            {
                "change_type": "needs_review",
                "confidence": "low",
                "reason": "ASR mơ hồ — có thể 'đặc trưng'; cần nghe lại",
                "trading_term_flag": False,
                "needs_relisten": True,
                "suspicious": True,
            }
        )

    if "Tiểu đa Airdrop" in t:
        new_t = t.replace("Tiểu đa", "Tiêu đề")
        fixes.append(
            {
                "change_type": "asr_term",
                "confidence": "medium",
                "reason": "ASR: Tiểu đa → Tiêu đề",
                "trading_term_flag": True,
                "needs_relisten": False,
            }
        )
        t = new_t

    if "EchoShip" in t:
        new_t = t.replace("EchoShip", "Ecosystem")
        fixes.append(
            {
                "change_type": "asr_term",
                "confidence": "low",
                "reason": "ASR: EchoShip → Ecosystem (đọc menu web, chưa chắc)",
                "trading_term_flag": True,
                "needs_relisten": True,
                "suspicious": True,
            }
        )
        t = new_t

    if "sập segue" in t:
        fixes.append(
            {
                "change_type": "needs_review",
                "confidence": "low",
                "reason": "ASR: 'segue' không rõ — cần nghe lại",
                "trading_term_flag": True,
                "needs_relisten": True,
                "suspicious": True,
            }
        )

    if "dã bóp sọt" in t:
        new_t = t.replace("dã bóp sọt", "dump bóp spot")
        fixes.append(
            {
                "change_type": "asr_term",
                "confidence": "low",
                "reason": "ASR: dã bóp sọt → dump bóp spot (slang trading)",
                "trading_term_flag": True,
                "needs_relisten": True,
            }
        )
        t = new_t

    if "mạnh vẽ" in t:
        new_t = t.replace("mạnh vẽ", "bánh vẽ")
        fixes.append(
            {
                "change_type": "asr_term",
                "confidence": "medium",
                "reason": "ASR: mạnh vẽ → bánh vẽ",
                "trading_term_flag": False,
                "needs_relisten": False,
            }
        )
        t = new_t

    if "đẻ quả mẹ logo" in t:
        new_t = t.replace("đẻ quả mẹ logo", "để quả logo")
        fixes.append(
            {
                "change_type": "asr_term",
                "confidence": "medium",
                "reason": "ASR: đẻ quả mẹ → để quả",
                "trading_term_flag": False,
                "needs_relisten": False,
            }
        )
        t = new_t

    for pattern, repl, ctype, reason, conf, trading, needs_relisten in replacements:
        new_t, n = re.subn(pattern, repl, t)
        if n > 0 and new_t != t:
            fixes.append(
                {
                    "change_type": ctype,
                    "confidence": conf,
                    "reason": reason,
                    "trading_term_flag": trading,
                    "needs_relisten": needs_relisten,
                    "suspicious": needs_relisten and conf == "low",
                }
            )
            t = new_t

    return t, fixes


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

    edits: dict[int, dict] = {}
    suspicious_ids: list[str] = []

    prev_text = ""
    for seg in segments:
        idx = seg["segment_index"]
        raw_text = seg["text"]
        ai_text, fix_meta = apply_fixes(raw_text)

        if raw_text == prev_text and idx > 0:
            # Whisper lặp cùng câu liên tiếp (blog menu)
            suspicious_ids.append(seg["segment_id"])
            if ai_text == raw_text:
                edits[idx] = {
                    "ai_text": ai_text,
                    "change_type": "duplicate",
                    "confidence": "medium",
                    "reason": "ASR lặp câu giống segment trước (đọc menu web)",
                    "trading_term_flag": False,
                    "needs_relisten": False,
                    "suspicious": True,
                }
                continue

        prev_text = raw_text

        if ai_text != raw_text or fix_meta:
            entry: dict = {
                "ai_text": ai_text,
                "change_type": fix_meta[0]["change_type"] if fix_meta else "asr_term",
                "confidence": fix_meta[0]["confidence"] if fix_meta else "medium",
                "reason": "; ".join(f["reason"] for f in fix_meta) if fix_meta else "",
                "trading_term_flag": any(f.get("trading_term_flag") for f in fix_meta),
                "needs_relisten": any(f.get("needs_relisten") for f in fix_meta),
            }
            if any(f.get("suspicious") for f in fix_meta):
                entry["suspicious"] = True
                suspicious_ids.append(seg["segment_id"])
            edits[idx] = entry

    edits_json = json.dumps({str(k): v for k, v in edits.items()}, ensure_ascii=False)
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
    print(f"edits={len(edits)} suspicious_ids={len(suspicious_ids)}", file=sys.stderr)


if __name__ == "__main__":
    main()
