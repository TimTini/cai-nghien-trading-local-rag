"""Chỉ số chất lượng transcript — không LLM, dùng báo cáo và lọc đoạn ASR."""

from __future__ import annotations

import re

GARBAGE_CHARS_RE = re.compile(r"[\uFFFD\u200b\u00ad\u0000-\u001f]")
# Chữ có dấu tiếng Việt hoặc chữ Latin thường dùng trong trading
VIETNAMESE_CHAR_RE = re.compile(
    r"[àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ]"
)
SENTENCE_END_RE = re.compile(r"[.!?…][\s\"')\]]*$")
WORD_RE = re.compile(r"\b[\wàáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ]+\b", re.IGNORECASE)


def garbage_char_count(text: str) -> int:
    return len(GARBAGE_CHARS_RE.findall(text))


def vietnamese_diacritic_ratio(text: str) -> float:
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return 0.0
    with_tone = sum(1 for ch in letters if VIETNAMESE_CHAR_RE.match(ch))
    return with_tone / len(letters)


def readable_sentence_ratio(text: str) -> float:
    """Tỷ lệ câu có vẻ đọc được: có chữ, không toàn rác, kết thúc hoặc đủ dài."""

    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    if not parts:
        return 0.0
    ok = 0
    for part in parts:
        part = part.strip()
        if len(part) < 4:
            continue
        if garbage_char_count(part) > 0:
            continue
        words = WORD_RE.findall(part)
        if len(words) < 2:
            continue
        if SENTENCE_END_RE.search(part) or len(part) >= 40:
            ok += 1
    return ok / len(parts) if parts else 0.0


def segment_quality_score(text: str) -> dict[str, float | int]:
    return {
        "garbage_chars": garbage_char_count(text),
        "readable_sentence_ratio": readable_sentence_ratio(text),
        "vietnamese_diacritic_ratio": vietnamese_diacritic_ratio(text),
        "char_count": len(text),
    }


def segment_needs_asr_retry(text: str) -> bool:
    """Heuristic: đoạn có thể lợi từ transcribe lại clip audio (engine asr-reprocess)."""

    if garbage_char_count(text) > 0:
        return True
    if len(text.strip()) < 8:
        return True
    # ASR đôi khi ra câu không dấu — chỉ flag khi dài và gần như không có dấu Việt
    if len(text) >= 30 and vietnamese_diacritic_ratio(text) < 0.05:
        return True
    return False
