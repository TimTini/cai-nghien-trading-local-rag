#!/usr/bin/env python3
"""Build agent-direct edits for wave 8 videos (raw ASR only)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from agent_direct_raw_helpers import clean_video

SUBSCRIBE_GHIEN = "Hãy subscribe cho kênh Ghiền Mì Gõ Để không bỏ lỡ những video hấp dẫn"
SUBSCRIBE_DK = "Đăng ký kênh để ủng hộ kênh của mình nhé"
SUBSCRIBE_CB = "Các bạn hãy đăng ký kênh để ủng hộ kênh của mình nhé"
THANKS = "Cảm ơn các bạn đã theo dõi và hẹn gặp lại."
UUUUU = re.compile(r"^Uuuuu\.?$", re.I)
ANH_ONLY = re.compile(r"^anh\.?$", re.I)
GIBBERISH_MARKERS = re.compile(
    r"Você|cciones|дин|Pro mẹo|Bài Hát|away$|PewC|constrictor|Button giặo",
    re.I,
)


def hallucination(reason: str) -> dict:
    return {
        "ai_text": "",
        "change_type": "asr_hallucination",
        "confidence": "high",
        "reason": reason,
        "needs_relisten": True,
        "suspicious": True,
        "trading_term_flag": False,
    }


def hook_subscribe_thanks(
    seg: dict, raw_text: str, suspicious_ids: list[str]
) -> dict | None:
    t = raw_text.strip()
    if t in (SUBSCRIBE_GHIEN, SUBSCRIBE_DK, SUBSCRIBE_CB):
        return hallucination("Whisper hallucination subscribe (Ghiền Mì Gõ / đăng ký kênh)")
    if t == THANKS:
        return hallucination("Whisper lặp outro 'Cảm ơn các bạn...' (ASR loop)")
    if UUUUU.match(t):
        return hallucination("Whisper lặp 'Uuuuu' (ASR loop khi thao tác UI)")
    if ANH_ONLY.match(t):
        return hallucination("Whisper lặp 'anh' (ASR loop)")
    if GIBBERISH_MARKERS.search(raw_text) and len(raw_text) > 60:
        return hallucination("ASR đoạn lẫn ngôn ngữ / noise — cần nghe lại")
    return None


def clean_wui() -> None:
    rules = [
        (r"\bđồng coi\b", "đồng coin", "asr_term", "ASR: coi → coin", "high", True, False),
        (r"\bcoi khác\b", "coin khác", "asr_term", "ASR: coi → coin", "high", True, False),
        (r"\bBót\b", "Bot", "asr_term", "ASR: Bót → Bot", "high", True, False),
        (r"\bbót\b", "bot", "asr_term", "ASR: bót → bot", "high", True, False),
        (r"\bbóp\b", "bot", "asr_term", "ASR: bóp → bot", "high", True, False),
        (r"\bboss\b", "bot", "asr_term", "ASR: boss → bot", "high", True, False),
        (r"\bfutu\b", "futures", "asr_term", "ASR: futu → futures", "high", True, False),
        (r"\blưới sọt\b", "lưới short", "asr_term", "ASR: sọt → short", "high", True, False),
        (r"\bxây sọt\b", "short", "asr_term", "ASR: xây sọt → short", "medium", True, False),
        (r"\bốp vào\b", "áp vào", "asr_term", "ASR: ốp → áp (apply)", "high", False, False),
        (r"\bnốt lại\b", "note lại", "asr_term", "ASR: nốt → note", "medium", False, False),
        (r"\bcon DOC\b", "con DOGE", "asr_term", "ASR: DOC → DOGE", "medium", True, True),
        (r"\bAVAC\b", "AVAX", "asr_term", "ASR: AVAC → AVAX", "high", True, False),
        (r"\beasy này\b", "EA này", "asr_term", "ASR: easy → EA (Expert Advisor)", "low", True, True),
        (r"\bAn ban\b", "Ban đầu", "asr_term", "ASR: An ban → Ban đầu", "medium", False, False),
        (r"\bký quyết\b", "ký quỹ", "asr_term", "ASR: quyết → quỹ", "high", True, False),
        (r"\bcai phân\b", "cài phần", "asr_term", "ASR: cai → cài", "medium", False, False),
        (r"\btiểu xứ\b", "tiểu xảo", "asr_term", "ASR: xứ → xảo", "medium", False, False),
        (r"\btiểu xử\b", "tiểu xảo", "asr_term", "ASR: xử → xảo", "medium", False, False),
        (r"\bcái lấy\b", "cái nến", "asr_term", "ASR: lấy → nến", "medium", True, False),
        (r"\bHot P\b", "HOT", "asr_term", "ASR: Hot P → HOT token", "low", True, True),
    ]

    def hook(seg: dict, raw_text: str, suspicious_ids: list[str]) -> dict | None:
        custom = hook_subscribe_thanks(seg, raw_text, suspicious_ids)
        if custom:
            return custom
        if raw_text.strip().startswith("Ba bùa bi bù"):
            return hallucination("ASR mở đầu lặp vần điệu (noise) — cần nghe lại")
        return None

    clean_video("WUIEfxXn_jQ", extra_rules=rules, segment_hook=hook)


def clean_cuq() -> None:
    rules = [
        (r"\bboss\b", "bot", "asr_term", "ASR: boss → bot", "high", True, False),
        (r"\bBoss\b", "Bot", "asr_term", "ASR: Boss → Bot", "high", True, False),
        (r"\bbóp\b", "bot", "asr_term", "ASR: bóp → bot", "high", True, False),
        (r"\bbút\b", "bot", "asr_term", "ASR: bút → bot", "high", True, False),
        (r"\bđi xe\b", "đi trade", "asr_term", "ASR: xe → trade (slang stream)", "low", True, True),
        (r"\bđi xe 18\b", "đi trade 18", "asr_term", "ASR: xe → trade", "low", True, True),
        (r"\bxe mình\b", "trade mình", "asr_term", "ASR: xe → trade", "low", True, True),
        (r"\bxe cái\b", "trade cái", "asr_term", "ASR: xe → trade", "low", True, True),
        (r"\bxe lỗi\b", "trade lỗi", "asr_term", "ASR: xe → trade", "low", True, True),
        (r"\bxe chỉ\b", "trade chỉ", "asr_term", "ASR: xe → trade", "low", True, True),
        (r"\bxe này\b", "trade này", "asr_term", "ASR: xe → trade", "low", True, True),
        (r"\bxe lên\b", "trade lên", "asr_term", "ASR: xe → trade", "low", True, True),
        (r"\bxe dài\b", "trade dài", "asr_term", "ASR: xe → trade", "low", True, True),
        (r"\bxe bay\b", "trade bay", "asr_term", "ASR: xe → trade", "low", True, True),
        (r"\bxe không\b", "trade không", "asr_term", "ASR: xe → trade", "low", True, True),
        (r"\bphu quý\b", "phú quý", "asr_term", "ASR: phu → phú", "medium", False, False),
        (r"\bMẹy\b", "Mình", "asr_term", "ASR: Mẹy → Mình", "high", False, False),
        (r"\bMẹy vô\b", "Mình vào", "asr_term", "ASR: Mẹy vô → Mình vào", "high", False, False),
        (r"\bđào pi\b", "đào P", "asr_term", "ASR: pi → P (không phải Pi Network ở đây)", "low", False, True),
    ]

    def hook(seg: dict, raw_text: str, suspicious_ids: list[str]) -> dict | None:
        custom = hook_subscribe_thanks(seg, raw_text, suspicious_ids)
        if custom:
            return custom
        if raw_text.strip() in ("илось", "splendid"):
            return hallucination("ASR noise / foreign fragment")
        return None

    clean_video("Cuqbd2TwP-I", extra_rules=rules, segment_hook=hook)


def clean_zoc() -> None:
    rules = [
        (r"\bchạc\b", "chart", "asr_term", "ASR: chạc → chart", "high", True, False),
        (r"\bChạc\b", "Chart", "asr_term", "ASR: Chạc → Chart", "high", True, False),
        (r"\bđồng block\b", "đồng coin", "asr_term", "ASR: block → coin", "medium", True, False),
        (r"\bBNN\b", "Binance", "asr_term", "ASR: BNN → Binance", "high", True, False),
        (r"\bOkik\b", "OKX", "brand_fix", "ASR: Okik → OKX", "high", True, False),
        (r"\bsản OKB\b", "sàn OKX", "asr_term", "ASR: sản → sàn", "high", True, False),
        (r"\bsản BNN\b", "sàn Binance", "asr_term", "ASR: sản → sàn", "high", True, False),
        (r"\bsản khác\b", "sàn khác", "asr_term", "ASR: sản → sàn", "high", True, False),
        (r"\bTP slot\b", "TP/SL", "asr_term", "ASR: TP slot → TP/SL", "medium", True, False),
        (r"\btp-slot\b", "TP/SL", "asr_term", "ASR: tp-slot → TP/SL", "medium", True, False),
        (r"\bPoly chỉ đăng\b", "Poloniex", "asr_term", "ASR: Poly → Poloniex (chưa chắc)", "low", True, True),
        (r"\bbất đồng dịch\b", "biến động", "asr_term", "ASR: bất đồng dịch → biến động (tab)", "low", True, True),
        (r"\bđánh future\b", "đánh futures", "asr_term", "ASR: future → futures", "high", True, False),
        (r"\bZKG\b", "ZK", "asr_term", "ASR: ZKG → ZK (token)", "medium", True, True),
    ]
    clean_video("zoc_pp4uUIQ", extra_rules=rules, segment_hook=hook_subscribe_thanks)


def clean_wsi() -> None:
    rules = [
        (r"\bphun quỹ\b", "vốn chung", "asr_term", "ASR: phun quỹ → pool vốn (cross margin)", "medium", True, True),
        (r"\bmazin\b", "margin", "asr_term", "ASR: mazin → margin", "high", True, False),
        (r"\bMazin\b", "Margin", "asr_term", "ASR: Mazin → Margin", "high", True, False),
        (r"\bSTOLOT\b", "stop loss", "asr_term", "ASR: STOLOT → stop loss", "high", True, False),
        (r"\bstop-lot\b", "stop loss", "asr_term", "ASR: stop-lot → stop loss", "high", True, False),
        (r"\bdp-siteío\b", "take profit", "asr_term", "ASR: dp-siteío → take profit (noise)", "low", True, True),
        (r"\btrốn lãi\b", "chốt lãi", "asr_term", "ASR: trốn → chốt", "high", True, False),
        (r"\bSL email\b", "SL", "asr_term", "ASR: SL email → SL (noise)", "medium", True, False),
        (r"\bMakito\b", "market", "asr_term", "ASR: Makito → market", "high", True, False),
        (r"\bđạt được\b", "đặt được", "asr_term", "ASR: đạt → đặt (đặt giá)", "medium", True, False),
        (r"\bngon th이었\b", "ngon chưa", "asr_term", "ASR: lẫn Hàn → ngon chưa", "low", False, True),
        (r"\btí当然\b", "tí thôi", "asr_term", "ASR: 当然 noise → tí thôi", "low", False, True),
        (r"\bmở думa\b", "mở chart", "asr_term", "ASR: думa → chart", "low", True, True),
        (r"\bbên support\b", "bên spot", "asr_term", "ASR: support → spot", "medium", True, False),
    ]

    def hook(seg: dict, raw_text: str, suspicious_ids: list[str]) -> dict | None:
        custom = hook_subscribe_thanks(seg, raw_text, suspicious_ids)
        if custom:
            return custom
        t = raw_text.strip()
        if t in ("add", "que", "well", "db", "looks", "Lâng", "requires", "là", "cciones"):
            return hallucination("ASR noise fragment cuối video")
        if re.match(r"^[a-zA-Z]{1,12}$", t) and t.lower() not in ("sl", "ok"):
            return hallucination("ASR noise fragment (latin)")
        return None

    clean_video("wsiRxlLpD5E", extra_rules=rules, segment_hook=hook)


def clean_8t6() -> None:
    rules = [
        (r"\bpin eo\b", "PnL", "asr_term", "ASR: pin eo → PnL", "high", True, False),
        (r"\bbên support\b", "bên spot", "asr_term", "ASR: support → spot wallet", "medium", True, False),
        (r"\bbên future\b", "bên futures", "asr_term", "ASR: future → futures", "high", True, False),
        (r"\bđiểm bốt\b", "điểm bot", "asr_term", "ASR: bốt → bot", "high", True, False),
        (r"\bcon bót\b", "con bot", "asr_term", "ASR: bót → bot", "high", True, False),
        (r"\bbót dương\b", "bot dương", "asr_term", "ASR: bót → bot", "high", True, False),
        (r"\bbót âm\b", "bot âm", "asr_term", "ASR: bót → bot", "high", True, False),
        (r"\bTCM\b", "TCN", "asr_term", "ASR: TCM → TCN (team)", "medium", False, False),
        (r"\bHọc dụng\b", "Hữu dụng", "asr_term", "ASR: Học → Hữu", "medium", False, False),
    ]

    def hook(seg: dict, raw_text: str, suspicious_ids: list[str]) -> dict | None:
        custom = hook_subscribe_thanks(seg, raw_text, suspicious_ids)
        if custom:
            return custom
        if re.fullmatch(r"[1-8](,[1-8])*", raw_text.replace(" ", "")):
            return hallucination("Whisper đếm số lặp (ASR loop)")
        return None

    clean_video("8T6VUZ1Q2EE", extra_rules=rules, segment_hook=hook)


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
        "WUIEfxXn_jQ": clean_wui,
        "Cuqbd2TwP-I": clean_cuq,
        "zoc_pp4uUIQ": clean_zoc,
        "wsiRxlLpD5E": clean_wsi,
        "8T6VUZ1Q2EE": clean_8t6,
    }
    fn = fns.get(video_id)
    if not fn:
        raise SystemExit(f"Unknown video: {video_id}")
    fn()


if __name__ == "__main__":
    main()
