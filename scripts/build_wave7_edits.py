#!/usr/bin/env python3
"""Build agent-direct edits for wave 7 videos (raw ASR only)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from agent_direct_raw_helpers import clean_video

THANKS = "Cảm ơn các bạn đã theo dõi và hẹn gặp lại."
NAY_ONLY = re.compile(r"^Này\.?$", re.I)


def clean_j8j() -> None:
    rules = [
        (r"\bAIDOC\b", "AIDOGE", "asr_term", "ASR: AIDOC → AIDOGE", "high", True, False),
        (r"\bai đó\b", "AIDOGE", "asr_term", "ASR: ai đó → AIDOGE", "medium", True, True),
        (r"\bđi xây dương\b", "đi DCA dương", "asr_term", "ASR: xây dương → DCA dương", "medium", True, True),
        (r"\bxây dương\b", "DCA dương", "asr_term", "ASR: xây dương → DCA dương", "medium", True, True),
        (r"\bcho em lo\b", "cho em long", "asr_term", "ASR: lo → long", "high", True, False),
        (r"\blong AIDOC\b", "long AIDOGE", "asr_term", "ASR: AIDOC → AIDOGE", "high", True, False),
        (r"\bcây dâu\b", "cây đáy", "asr_term", "ASR: dâu → đáy", "high", True, False),
        (r"\bcái dâu\b", "cái đáy", "asr_term", "ASR: dâu → đáy", "high", True, False),
        (r"\bsảm\b", "xả", "asr_term", "ASR: sảm → xả (pullback)", "medium", True, False),
        (r"\bsả ngược\b", "xả ngược", "asr_term", "ASR: sả → xả", "high", True, False),
        (r"\bchặt D\b", "chart D", "asr_term", "ASR: chặt D → chart D (daily)", "medium", True, False),
        (r"\bvô luôn\b", "volume", "asr_term", "ASR: vô luôn → volume", "medium", True, True),
        (r"\bcon lợn\b", "con coin", "asr_term", "ASR: lợn → coin (slang)", "low", True, True),
    ]
    clean_video("J8jnLls7Fe4", extra_rules=rules)


def clean_vnw() -> None:
    rules = [
        (r"\bSock\b", "Shock", "asr_term", "ASR: Sock → Shock (giai đoạn thị trường)", "high", True, False),
        (r"\bVolume đổi biến\b", "Volume biến động", "asr_term", "ASR: đổi biến → biến động", "high", True, False),
        (r"\bnhập môi spot\b", "mua spot", "asr_term", "ASR: nhập môi → mua (spot)", "medium", True, False),
        (r"\bcoin môi\b", "coin mới", "asr_term", "ASR: môi → mới", "medium", True, False),
        (r"\bCap này\b", "Cap này", "asr_term", "Giữ Cap (market cap)", "high", True, False),
        (r"\b16Z\b", "16Z", "asr_term", "Token 16Z (giữ nguyên)", "high", True, False),
    ]
    clean_video("VNwgUmnJ7Do", extra_rules=rules)


def clean_uo7() -> None:
    rules = [
        (r"\blừng ngây\b", "Lường đây", "asr_term", "ASR: lừng ngây → Lường đây (host)", "high", False, False),
        (r"\blừng đây\b", "Lường đây", "asr_term", "ASR: lừng → Lường (host)", "high", False, False),
        (r"\blừng nhắc\b", "Lường nhắc", "asr_term", "ASR: lừng → Lường (host)", "high", False, False),
        (r"\bhâu Bitcoin\b", "hold Bitcoin", "asr_term", "ASR: hâu → hold", "high", True, False),
        (r"\bquý ETF\b", "quỹ ETF", "asr_term", "ASR: quý → quỹ", "high", True, False),
        (r"\bvôn hóa\b", "vốn hóa", "asr_term", "ASR: vôn → vốn", "high", True, False),
        (r"\btài trình\b", "tài chính", "asr_term", "ASR: trình → chính", "high", False, False),
        (r"\bphép giữ\b", "Fed giữ", "asr_term", "ASR: phép → Fed (lãi suất)", "medium", True, True),
    ]
    clean_video("-Uo77NEuE-E", extra_rules=rules)


def hook_xxx(seg: dict, raw_text: str, suspicious_ids: list[str]) -> dict | None:
    if raw_text.strip() == THANKS:
        return {
            "ai_text": "",
            "change_type": "asr_hallucination",
            "confidence": "high",
            "reason": "Whisper lặp outro 'Cảm ơn các bạn...' (ASR loop)",
            "needs_relisten": True,
            "suspicious": True,
            "trading_term_flag": False,
        }
    if NAY_ONLY.match(raw_text.strip()):
        return {
            "ai_text": "",
            "change_type": "asr_hallucination",
            "confidence": "high",
            "reason": "Whisper lặp 'Này' (ASR loop)",
            "needs_relisten": True,
            "suspicious": True,
            "trading_term_flag": False,
        }
    return None


def clean_xxx() -> None:
    rules = [
        (r"\blực mùa\b", "lực mua", "asr_term", "ASR: mùa → mua", "high", True, False),
        (r"\bđi coi\b", "đi coin", "asr_term", "ASR: coi → coin", "medium", True, False),
        (r"\bcái lấy\b", "cái nến", "asr_term", "ASR: lấy → nến", "medium", True, False),
        (r"\bẩm buổi\b", "offline buổi", "asr_term", "ASR: ẩm → offline (sự kiện)", "low", False, True),
    ]
    clean_video("XXXBDkFA0BU", extra_rules=rules, segment_hook=hook_xxx)


def clean_esa() -> None:
    rules = [
        (r"\bsản KX\b", "sàn KX", "asr_term", "ASR: sản → sàn", "high", True, False),
        (r"\bsản giao dịch\b", "sàn giao dịch", "asr_term", "ASR: sản → sàn", "high", True, False),
        (r"\bsản crypto\b", "sàn crypto", "asr_term", "ASR: sản → sàn", "high", True, False),
        (r"\bsản OKX\b", "sàn OKX", "asr_term", "ASR: sản → sàn", "high", True, False),
        (r"\bLinky D\b", "LinkID", "asr_term", "ASR: Linky D → LinkID (định danh số, chưa chắc)", "low", True, True),
        (r"\bVP Bank S\b", "VPBankS", "asr_term", "ASR: VP Bank S → VPBankS", "medium", False, False),
    ]
    clean_video("ESang1g9kgc", extra_rules=rules)


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
        "J8jnLls7Fe4": clean_j8j,
        "VNwgUmnJ7Do": clean_vnw,
        "-Uo77NEuE-E": clean_uo7,
        "XXXBDkFA0BU": clean_xxx,
        "ESang1g9kgc": clean_esa,
    }
    fn = fns.get(video_id)
    if not fn:
        raise SystemExit(f"Unknown video: {video_id}")
    fn()


if __name__ == "__main__":
    main()
