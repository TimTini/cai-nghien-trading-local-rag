#!/usr/bin/env python3
"""Build agent-direct edits for wave 11 videos (raw ASR only)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from agent_direct_raw_helpers import clean_video
from build_wave10_edits import OKX_RULES
from build_wave8_edits import hallucination, hook_subscribe_thanks


def clean_lhyl() -> None:
    rules = OKX_RULES + [
        (r"\bOKex\b", "OKX", "brand_fix", "ASR: OKex → OKX", "high", True, False),
        (r"\bsang coi\b", "sang coin", "asr_term", "ASR: coi → coin", "high", True, False),
        (r"\bSang coi\b", "Sang coin", "asr_term", "ASR: coi → coin", "high", True, False),
        (r"\bchơi coi\b", "chơi coin", "asr_term", "ASR: coi → coin", "high", True, False),
        (r"\bđồng coi\b", "đồng coin", "asr_term", "ASR: coi → coin", "high", True, False),
        (r"\bcon coi\b", "con coin", "asr_term", "ASR: coi → coin", "high", True, False),
        (r"\bcoi sàn\b", "coin sàn", "asr_term", "ASR: coi → coin", "high", True, False),
        (r"\bchết coi\b", "chết coin", "asr_term", "ASR: coi → coin", "high", True, False),
        (r"\bFuture\b", "futures", "asr_term", "ASR: Future → futures", "high", True, False),
        (r"\bsọt\b", "short", "asr_term", "ASR: sọt → short", "high", True, False),
        (r"\bđi sọt\b", "đi short", "asr_term", "ASR: sọt → short", "high", True, False),
        (r"\bvào sọt\b", "vào short", "asr_term", "ASR: sọt → short", "high", True, False),
    ]

    def hook(seg: dict, raw_text: str, suspicious_ids: list[str]) -> dict | None:
        return hook_subscribe_thanks(seg, raw_text, suspicious_ids)

    clean_video("LHYl6-zie3k", extra_rules=rules, segment_hook=hook)


def clean_w5kd() -> None:
    rules = OKX_RULES + [
        (r"\bđể sót\b", "để short", "asr_term", "ASR: sót → short", "high", True, False),
        (r"\bsót được\b", "short được", "asr_term", "ASR: sót → short", "high", True, False),
    ]
    clean_video("W5KdMzVaH3o", extra_rules=rules, segment_hook=hook_subscribe_thanks)


def clean_yifh() -> None:
    rules = OKX_RULES + [
        (r"\bBoss Trading\b", "Bot Trading", "asr_term", "ASR: Boss → Bot (trading bot)", "high", True, False),
        (r"\bBoss\b", "Bot", "asr_term", "ASR: Boss → Bot", "high", True, False),
        (r"\bboss\b", "bot", "asr_term", "ASR: boss → bot", "high", True, False),
        (r"\bbót\b", "bot", "asr_term", "ASR: bót → bot", "high", True, False),
        (r"\bBót\b", "Bot", "asr_term", "ASR: Bót → Bot", "high", True, False),
        (r"\bOKEx\b", "OKX", "brand_fix", "ASR: OKEx → OKX", "high", True, False),
        (r"\bfuture\b", "futures", "asr_term", "ASR: future → futures", "high", True, False),
        (r"\bFuture\b", "futures", "asr_term", "ASR: Future → futures", "high", True, False),
    ]
    clean_video("yIFHafjkWnw", extra_rules=rules, segment_hook=hook_subscribe_thanks)


def clean_notkb() -> None:
    rules = OKX_RULES + [
        (r"\bbóp\b", "bot", "asr_term", "ASR: bóp → bot", "high", True, False),
        (r"\bBóp\b", "Bot", "asr_term", "ASR: Bóp → Bot", "high", True, False),
        (r"\bboss\b", "bot", "asr_term", "ASR: boss → bot", "high", True, False),
        (r"\bBoss\b", "Bot", "asr_term", "ASR: Boss → Bot", "high", True, False),
        (r"\bFuture\b", "futures", "asr_term", "ASR: Future → futures", "high", True, False),
        (r"\bfuture\b", "futures", "asr_term", "ASR: future → futures", "high", True, False),
        (r"\bđồng coi\b", "đồng coin", "asr_term", "ASR: coi → coin", "high", True, False),
        (r"\bcòn sót\b", "còn short", "asr_term", "ASR: sót → short", "high", True, False),
        (r"\bhình dung coi\b", "hình dung coin", "asr_term", "ASR: coi → coin", "medium", True, False),
        (r"\blưới Future\b", "lưới futures", "asr_term", "ASR: Future → futures", "high", True, False),
    ]
    clean_video("NoTkbR7_Mwg", extra_rules=rules, segment_hook=hook_subscribe_thanks)


def clean_pfj5() -> None:
    rules = OKX_RULES + [
        (r"\bMaket\b", "Market", "asr_term", "ASR: Maket → Market", "medium", True, False),
    ]

    def hook(seg: dict, raw_text: str, suspicious_ids: list[str]) -> dict | None:
        custom = hook_subscribe_thanks(seg, raw_text, suspicious_ids)
        if custom:
            return custom
        if re.search(r"ra coi$", raw_text.strip(), re.I):
            return {
                "ai_text": re.sub(r"ra coi$", "ra xem", raw_text.strip(), flags=re.I),
                "change_type": "asr_term",
                "confidence": "high",
                "reason": "ASR: ra coi → ra xem (không phải coin)",
                "needs_relisten": False,
                "trading_term_flag": False,
            }
        return None

    clean_video("PfJ5hfGwL8g", extra_rules=rules, segment_hook=hook)


def main() -> None:
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("video_id", nargs="?", default=None)
    p.add_argument("--video-id", dest="video_id_opt")
    args = p.parse_args()
    video_id = args.video_id or args.video_id_opt
    if not video_id:
        p.error("video_id required")
    fns = {
        "LHYl6-zie3k": clean_lhyl,
        "W5KdMzVaH3o": clean_w5kd,
        "yIFHafjkWnw": clean_yifh,
        "NoTkbR7_Mwg": clean_notkb,
        "PfJ5hfGwL8g": clean_pfj5,
    }
    fn = fns.get(video_id)
    if not fn:
        raise SystemExit(f"Unknown video: {video_id}")
    fn()


if __name__ == "__main__":
    main()
