"""Làm sạch bảo thủ: rule + glossary/confusion map + dấu câu — không LLM."""

from __future__ import annotations

from pathlib import Path

from .cleaner import _has_trading_context, _numbers_signature, rule_clean_text
from .glossary_fixes import apply_confusion_fixes, fix_vn_punctuation_spacing, load_confusion_entries
from .schema import QualitySegment, SegmentChange


def _attach_segment_meta(
    segment: QualitySegment,
    changes: list[SegmentChange],
) -> list[SegmentChange]:
    out: list[SegmentChange] = []
    for change in changes:
        trading = _has_trading_context(segment.text) or _has_trading_context(change.ai_text)
        nums_changed = _numbers_signature(change.raw_text) != _numbers_signature(change.ai_text)
        confidence = change.confidence
        needs_relisten = change.needs_relisten
        if trading and nums_changed:
            confidence = "low"
            needs_relisten = True
            change = SegmentChange(
                segment_id=segment.segment_id,
                segment_index=segment.segment_index,
                start=segment.start,
                end=segment.end,
                raw_text=change.raw_text,
                ai_text=change.ai_text,
                change_type="trading_term",
                reason="Có số/thuật ngữ trading — cần nghe lại trước khi chấp nhận",
                confidence=confidence,
                needs_relisten=needs_relisten,
                trading_term_flag=True,
            )
        else:
            change = SegmentChange(
                segment_id=segment.segment_id,
                segment_index=segment.segment_index,
                start=segment.start,
                end=segment.end,
                raw_text=change.raw_text,
                ai_text=change.ai_text,
                change_type=change.change_type,
                reason=change.reason,
                confidence=confidence,
                needs_relisten=needs_relisten,
                trading_term_flag=trading,
            )
        out.append(change)
    return out


def refine_text(
    text: str,
    *,
    glossary_terms: list[str],
    confusion_entries: list[dict],
) -> tuple[str, list[SegmentChange]]:
    all_changes: list[SegmentChange] = []
    current = text

    cleaned, rule_changes = rule_clean_text(current)
    current = cleaned
    all_changes.extend(rule_changes)

    cleaned, punct_changes = fix_vn_punctuation_spacing(current)
    current = cleaned
    all_changes.extend(punct_changes)

    cleaned, map_changes = apply_confusion_fixes(current, confusion_entries, glossary_terms)
    current = cleaned
    all_changes.extend(map_changes)

    return current, all_changes


def refine_segment(
    segment: QualitySegment,
    *,
    root: Path | None,
    glossary_terms: list[str],
) -> tuple[QualitySegment, list[SegmentChange]]:
    entries = load_confusion_entries(root) if root else []
    cleaned_text, patch_changes = refine_text(
        segment.text,
        glossary_terms=glossary_terms,
        confusion_entries=entries,
    )
    if cleaned_text == segment.text:
        return segment, []

    return QualitySegment(
        segment_id=segment.segment_id,
        video_id=segment.video_id,
        title=segment.title,
        published_at=segment.published_at,
        start=segment.start,
        end=segment.end,
        text=cleaned_text,
        video_url=segment.video_url,
        source_type=segment.source_type,
        source_path=segment.source_path,
        language=segment.language,
        segment_index=segment.segment_index,
    ), _attach_segment_meta(segment, patch_changes)


def refine_all_segments(
    segments: list[QualitySegment],
    *,
    root: Path,
    glossary_terms: list[str] | None = None,
) -> tuple[list[QualitySegment], list[SegmentChange]]:
    glossary = glossary_terms or []
    cleaned_segments: list[QualitySegment] = []
    all_changes: list[SegmentChange] = []
    for segment in segments:
        updated, changes = refine_segment(segment, root=root, glossary_terms=glossary)
        cleaned_segments.append(updated)
        all_changes.extend(changes)
    return cleaned_segments, all_changes
