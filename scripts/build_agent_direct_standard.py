#!/usr/bin/env python3
"""Standard agent-direct clean: OKX_RULES + subscribe hook + auto-detected raw patterns."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from agent_direct_raw_helpers import clean_video
from build_wave10_edits import OKX_RULES
from build_wave8_edits import hook_subscribe_thanks
from build_wave9_edits import hook_loops

BASE = ROOT / "data" / "analysis" / "transcript_quality"

# Extra rules applied when pattern appears in raw transcript
AUTO_RULES: list[tuple[str, str, str, str, str, bool, bool]] = [
    (r"\bBoss Trading\b", "Bot Trading", "asr_term", "ASR: Boss → Bot", "high", True, False),
    (r"\bBoss\b", "Bot", "asr_term", "ASR: Boss → Bot", "high", True, False),
    (r"\bboss\b", "bot", "asr_term", "ASR: boss → bot", "high", True, False),
    (r"\bbóp\b", "bot", "asr_term", "ASR: bóp → bot", "high", True, False),
    (r"\bBóp\b", "Bot", "asr_term", "ASR: Bóp → Bot", "high", True, False),
    (r"\bBót\b", "Bot", "asr_term", "ASR: Bót → Bot", "high", True, False),
    (r"\bbót\b", "bot", "asr_term", "ASR: bót → bot", "high", True, False),
    (r"\bOKEx\b", "OKX", "brand_fix", "ASR: OKEx → OKX", "high", True, False),
    (r"\bOKex\b", "OKX", "brand_fix", "ASR: OKex → OKX", "high", True, False),
    (r"\bFuture\b", "futures", "asr_term", "ASR: Future → futures", "high", True, False),
    (r"\blưới Future\b", "lưới futures", "asr_term", "ASR: Future → futures", "high", True, False),
    (r"\bđồng coi\b", "đồng coin", "asr_term", "ASR: coi → coin", "high", True, False),
    (r"\bsang coi\b", "sang coin", "asr_term", "ASR: coi → coin", "high", True, False),
    (r"\bchơi coi\b", "chơi coin", "asr_term", "ASR: coi → coin", "high", True, False),
    (r"\bcoi sàn\b", "coin sàn", "asr_term", "ASR: coi → coin", "high", True, False),
    (r"\bsọt\b", "short", "asr_term", "ASR: sọt → short", "high", True, False),
    (r"\bđể sót\b", "để short", "asr_term", "ASR: sót → short", "high", True, False),
    (r"\bcòn sót\b", "còn short", "asr_term", "ASR: sót → short", "high", True, False),
    (r"\bvào sọt\b", "vào short", "asr_term", "ASR: sọt → short", "high", True, False),
    (r"\bBitgett\b", "Bitget", "brand_fix", "ASR: Bitgett → Bitget", "high", True, False),
    (r"\bBinace\b", "Binance", "brand_fix", "ASR: Binace → Binance", "high", True, False),
    (r"\bTrading View\b", "TradingView", "asr_term", "ASR: Trading View → TradingView", "high", True, False),
    (r"\bK View\b", "TradingView", "asr_term", "ASR: K View → TradingView", "medium", True, False),
]


def load_raw_text(video_id: str) -> str:
    folder = BASE / video_id
    with (folder / "raw.meta.json").open(encoding="utf-8") as f:
        raw_meta = json.load(f)
    raw_file = folder / raw_meta["raw_file"]
    return raw_file.read_text(encoding="utf-8")


def rules_for_video(video_id: str) -> list[tuple[str, str, str, str, str, bool, bool]]:
    blob = load_raw_text(video_id)
    rules = list(OKX_RULES)
    seen: set[str] = set()
    for item in AUTO_RULES:
        pat = item[0]
        if pat in seen:
            continue
        if re.search(pat, blob, re.I):
            rules.append(item)
            seen.add(pat)
    return rules


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("video_id", nargs="?", default=None)
    p.add_argument("--video-id", dest="video_id_opt")
    p.add_argument("--hook-loops", action="store_true", help="Use hook_loops (Này/gibberish) vs subscribe only")
    args = p.parse_args()
    video_id = args.video_id or args.video_id_opt
    if not video_id:
        p.error("video_id required")
    hook = hook_loops if args.hook_loops else hook_subscribe_thanks
    rules = rules_for_video(video_id)
    clean_video(video_id, extra_rules=rules, segment_hook=hook)


if __name__ == "__main__":
    main()
