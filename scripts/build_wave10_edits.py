#!/usr/bin/env python3
"""Build agent-direct edits for wave 10 videos (raw ASR only)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from agent_direct_raw_helpers import clean_video
from build_wave8_edits import hallucination, hook_subscribe_thanks

OKX_RULES: list[tuple[str, str, str, str, str, bool, bool]] = [
    (r"\bbức giá\b", "bước giá", "asr_term", "ASR: bức → bước", "high", True, False),
    (r"\bpin eo\b", "PnL", "asr_term", "ASR: pin eo → PnL", "high", True, False),
    (r"\bđồng coi\b", "đồng coin", "asr_term", "ASR: coi → coin", "high", True, False),
    (r"\bmua coi\b", "mua coin", "asr_term", "ASR: coi → coin", "high", True, False),
    (r"\bsố coi\b", "số coin", "asr_term", "ASR: coi → coin", "high", True, False),
    (r"\bcháy sót\b", "short", "asr_term", "ASR: cháy sót → short", "high", True, False),
    (r"\bsọt\b", "short", "asr_term", "ASR: sọt → short", "high", True, False),
    (r"\bphân in\b", "phân kỳ", "asr_term", "ASR: phân in → phân kỳ", "medium", True, False),
    (r"\bMón nấn\b", "môn này", "asr_term", "ASR: Món nấn → môn (noise)", "low", False, True),
]


def clean_jav() -> None:
    rules = OKX_RULES + [
        (r"\bCard\b", "Cap", "asr_term", "ASR: Card → Cap (market cap)", "high", True, False),
        (r"\bMarket Card\b", "Market Cap", "asr_term", "ASR: Card → Cap", "high", True, False),
        (r"\bcoinmarketcard\b", "coinmarketcap", "brand_fix", "ASR: coinmarketcard → coinmarketcap", "high", True, False),
        (r"\bMakicat\b", "Market Cap", "asr_term", "ASR: Makicat → Market Cap", "high", True, False),
        (r"\bBitgett\b", "Bitget", "brand_fix", "ASR: Bitgett → Bitget", "high", True, False),
        (r"\bgóc vượng\b", "gốc Vượng", "asr_term", "ASR: góc → gốc (Phạm Nhật Vượng)", "medium", False, False),
        (r"\bLiquid\b", "liquidation", "asr_term", "ASR: Liquid → liquidation heatmap", "medium", True, False),
    ]
    clean_video("jAjvfvfxUIQ", extra_rules=rules, segment_hook=hook_subscribe_thanks)


def clean_lwn() -> None:
    rules = OKX_RULES + [
        (r"\bfuture nó\b", "futures nó", "asr_term", "ASR: future → futures", "high", True, False),
        (r"\blưới future\b", "lưới futures", "asr_term", "ASR: future → futures", "high", True, False),
        (r"\bđi xe học\b", "đi học", "asr_term", "ASR: xe → (noise)", "low", False, True),
        (r"\btrên OK\b", "trên OKX", "brand_fix", "ASR: OK → OKX", "high", True, False),
    ]
    clean_video("lWNkkd6WciE", extra_rules=rules, segment_hook=hook_subscribe_thanks)


def clean_dk0() -> None:
    clean_video("DK0HHV85TVU", extra_rules=OKX_RULES, segment_hook=hook_subscribe_thanks)


def clean_hdq() -> None:
    rules = OKX_RULES + [
        (r"\bK View\b", "TradingView", "asr_term", "ASR: K View → TradingView", "medium", True, False),
        (r"\bgiật dâu\b", "giật đáy", "asr_term", "ASR: dâu → đáy", "high", True, False),
        (r"\btích bờ\b", "take profit", "asr_term", "ASR: tích bờ → take profit", "low", True, True),
    ]

    def hook(seg: dict, raw_text: str, suspicious_ids: list[str]) -> dict | None:
        custom = hook_subscribe_thanks(seg, raw_text, suspicious_ids)
        if custom:
            return custom
        if re.search(r"fierino|đ簸|1ict", raw_text):
            return hallucination("ASR noise / foreign fragment")
        return None

    clean_video("hdquiVxJJlo", extra_rules=rules, segment_hook=hook)


def clean_ejb() -> None:
    rules = OKX_RULES + [
        (r"\bvkn\b", "VN", "asr_term", "ASR: vkn → VN (noise)", "low", False, True),
    ]

    def hook(seg: dict, raw_text: str, suspicious_ids: list[str]) -> dict | None:
        custom = hook_subscribe_thanks(seg, raw_text, suspicious_ids)
        if custom:
            return custom
        if raw_text.strip() in ("vkn", "nó", "các", "à à"):
            return hallucination("ASR noise fragment")
        return None

    clean_video("EjBqQm1i86I", extra_rules=rules, segment_hook=hook)


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
        "jAjvfvfxUIQ": clean_jav,
        "lWNkkd6WciE": clean_lwn,
        "DK0HHV85TVU": clean_dk0,
        "hdquiVxJJlo": clean_hdq,
        "EjBqQm1i86I": clean_ejb,
    }
    fn = fns.get(video_id)
    if not fn:
        raise SystemExit(f"Unknown video: {video_id}")
    fn()


if __name__ == "__main__":
    main()
