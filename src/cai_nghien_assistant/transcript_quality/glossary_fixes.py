"""Sửa ASR bảo thủ theo glossary kênh và bảng nhầm lẫn cố định."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ..config import load_project_config
from .schema import SegmentChange


def _word_boundary_pattern(phrase: str) -> re.Pattern[str]:
    escaped = re.escape(phrase.strip())
    return re.compile(rf"(?<!\w){escaped}(?!\w)", re.IGNORECASE)


def load_confusion_entries(root: Path) -> list[dict[str, Any]]:
    config = load_project_config(root)
    tq = config.get("transcript_quality") or {}
    rel = str(tq.get("asr_confusion_map") or "data/analysis/transcript_quality/asr_confusion_map.json")
    path = root / rel
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return list(data.get("replacements") or [])


def apply_confusion_fixes(
    text: str,
    entries: list[dict[str, Any]],
    glossary_terms: list[str],
) -> tuple[str, list[SegmentChange]]:
    glossary_lower = {t.lower() for t in glossary_terms}
    changes: list[SegmentChange] = []
    result = text

    for entry in entries:
        wrong = str(entry.get("wrong") or "").strip()
        right = str(entry.get("right") or "").strip()
        if not wrong or not right or wrong.lower() == right.lower():
            continue
        requires_glossary = bool(entry.get("requires_glossary", True))
        if requires_glossary and right.lower() not in glossary_lower:
            continue
        pattern = _word_boundary_pattern(wrong)
        if not pattern.search(result):
            continue
        new_text = pattern.sub(right, result)
        if new_text == result:
            continue
        changes.append(
            SegmentChange(
                segment_id="",
                segment_index=0,
                start=0.0,
                end=0.0,
                raw_text=result,
                ai_text=new_text,
                change_type="glossary_fix",
                reason=f"ASR confusion map: {wrong} → {right}",
                confidence="medium" if requires_glossary else "high",
            )
        )
        result = new_text

    return result, changes


def fix_vn_punctuation_spacing(text: str) -> tuple[str, list[SegmentChange]]:
    """Chỉ khoảng trắng / dấu câu — không đổi từ vựng."""

    changes: list[SegmentChange] = []
    original = text
    cleaned = re.sub(r"\s+([,;:.!?])", r"\1", text)
    cleaned = re.sub(r"([,;:])([^\s])", r"\1 \2", cleaned)
    cleaned = re.sub(r"\.{4,}", "...", cleaned)
    if cleaned != original:
        changes.append(
            SegmentChange(
                segment_id="",
                segment_index=0,
                start=0.0,
                end=0.0,
                raw_text=original,
                ai_text=cleaned,
                change_type="punctuation",
                reason="Chuẩn khoảng trắng quanh dấu câu",
                confidence="high",
            )
        )
    return cleaned, changes
