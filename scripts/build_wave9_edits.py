#!/usr/bin/env python3
"""Build agent-direct edits for wave 9 videos (raw ASR only)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from agent_direct_raw_helpers import clean_video
from build_wave8_edits import hallucination, hook_subscribe_thanks

NAY_ONLY = re.compile(r"^Này\.?$", re.I)
GIBBERISH = re.compile(
    r"ch青|thoubec|lighthouse|hawthorn|lagço|Copay|recycle|splitsize|丸|tどう|DXDI|Zapata",
    re.I,
)


def hook_loops(seg: dict, raw_text: str, suspicious_ids: list[str]) -> dict | None:
    custom = hook_subscribe_thanks(seg, raw_text, suspicious_ids)
    if custom:
        return custom
    t = raw_text.strip()
    if NAY_ONLY.match(t):
        return hallucination("Whisper lặp 'Này' (ASR loop)")
    if GIBBERISH.search(raw_text):
        return hallucination("ASR lẫn ngôn ngữ / noise — cần nghe lại")
    if re.fullmatch(r"(à\s*){6,}", t.replace(" ", "")):
        return hallucination("Whisper lặp 'à' (ASR loop)")
    return None


def clean_mrq() -> None:
    rules = [
        (r"\bbót\b", "bot", "asr_term", "ASR: bót → bot", "high", True, False),
        (r"\bBót\b", "Bot", "asr_term", "ASR: Bót → Bot", "high", True, False),
        (r"\bsọt\b", "short", "asr_term", "ASR: sọt → short", "high", True, False),
        (r"\bđép\b", "đặt", "asr_term", "ASR: đép → đặt (margin)", "medium", True, False),
        (r"\bPi thủ\b", "Pi thợ", "asr_term", "ASR: thủ → thợ (miner slang)", "low", False, True),
        (r"\bbót pi\b", "bot Pi", "asr_term", "ASR: bót pi → bot Pi", "high", True, False),
        (r"\bTCR\b", "TCN", "asr_term", "ASR: TCR → TCN", "medium", False, False),
        (r"\bố rẻ\b", "ốc rẻ", "asr_term", "ASR: ố rẻ → ốc rẻ (cheap)", "low", True, True),
    ]
    clean_video("MRQqsFJZN3M", extra_rules=rules, segment_hook=hook_loops)


def clean_2cm() -> None:
    rules = [
        (r"\bSinh khoán\b", "chứng khoán", "asr_term", "ASR: Sinh → chứng", "high", False, False),
        (r"\bFuture mẻ\b", "Futures MEXC", "asr_term", "ASR: Future mẻ → Futures MEXC", "medium", True, True),
        (r"\bPII\b", "PIV", "asr_term", "ASR: PII → PIV (mã CK, chưa chắc)", "low", True, True),
        (r"\bcon PII\b", "cổ phiếu PIV", "asr_term", "ASR: PII → PIV", "low", True, True),
    ]
    clean_video("2cMePsKKn8g", extra_rules=rules, segment_hook=hook_subscribe_thanks)


def clean_uhf() -> None:
    rules = [
        (r"\bsàn gái\b", "sàn gate", "asr_term", "ASR: gái → gate (Gate.io)", "medium", True, True),
        (r"\blên gái\b", "lên Gate", "asr_term", "ASR: gái → Gate", "medium", True, True),
        (r"\bPi tơ\b", "Pi thôi", "asr_term", "ASR: tơ → thôi", "medium", False, False),
        (r"\bCato\b", "Kaito", "asr_term", "ASR: Cato → Kaito (dự án, chưa chắc)", "low", True, True),
        (r"\bAntenon\b", "Antler", "asr_term", "ASR: Antenon → Antler (VC, chưa chắc)", "low", False, True),
        (r"\bChaining\b", "Chainlink", "asr_term", "ASR: Chaining → Chainlink", "medium", True, True),
        (r"\bSonana\b", "Solana", "asr_term", "ASR: Sonana → Solana", "high", True, False),
        (r"\bXi này\b", "Sui này", "asr_term", "ASR: Xi → Sui", "low", True, True),
        (r"\bcoi cái\b", "xem cái", "asr_term", "ASR: coi → xem", "medium", False, False),
    ]
    clean_video("uHfkdDAM0LU", extra_rules=rules, segment_hook=hook_loops)


def clean_yqm() -> None:
    rules = [
        (r"\bpin eo\b", "PnL", "asr_term", "ASR: pin eo → PnL", "high", True, False),
        (r"\bbức giá\b", "bước giá", "asr_term", "ASR: bức → bước", "high", True, False),
        (r"\bnhân bức\b", "nhân bước", "asr_term", "ASR: bức → bước", "high", True, False),
        (r"\bquý lệnh\b", "ký quỹ", "asr_term", "ASR: quý lệnh → ký quỹ", "medium", True, False),
        (r"\bđẻ này\b", "đẹp này", "asr_term", "ASR: đẻ → đẹp", "medium", False, False),
    ]

    def hook(seg: dict, raw_text: str, suspicious_ids: list[str]) -> dict | None:
        custom = hook_loops(seg, raw_text, suspicious_ids)
        if custom:
            return custom
        if raw_text.strip() == "Vừa tạo à":
            return hallucination("Whisper lặp 'Vừa tạo à' (ASR loop)")
        return None

    clean_video("yQmpQ6M3g8A", extra_rules=rules, segment_hook=hook)


def clean_gfl() -> None:
    rules = [
        (r"\bbức giá\b", "bước giá", "asr_term", "ASR: bức → bước", "high", True, False),
        (r"\bBức giá\b", "Bước giá", "asr_term", "ASR: Bức → Bước", "high", True, False),
        (r"\bký quý\b", "ký quỹ", "asr_term", "ASR: quý → quỹ", "high", True, False),
        (r"\bký quyết\b", "ký quỹ", "asr_term", "ASR: quyết → quỹ", "high", True, False),
        (r"\bbót\b", "bot", "asr_term", "ASR: bót → bot", "high", True, False),
        (r"\bBOT\b", "bot", "asr_term", "Giữ bot", "high", True, False),
        (r"\bđồng an coi\b", "altcoin", "asr_term", "ASR: an coi → altcoin", "medium", True, False),
        (r"\bthí sinh\b", "học viên", "asr_term", "ASR: thí sinh → học viên (lớp)", "medium", False, False),
    ]
    clean_video("GfLvvIo7azg", extra_rules=rules, segment_hook=hook_loops)


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
        "MRQqsFJZN3M": clean_mrq,
        "2cMePsKKn8g": clean_2cm,
        "uHfkdDAM0LU": clean_uhf,
        "yQmpQ6M3g8A": clean_yqm,
        "GfLvvIo7azg": clean_gfl,
    }
    fn = fns.get(video_id)
    if not fn:
        raise SystemExit(f"Unknown video: {video_id}")
    fn()


if __name__ == "__main__":
    main()
