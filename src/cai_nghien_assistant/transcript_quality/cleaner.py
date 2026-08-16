"""Làm sạch transcript bảo thủ — rule-based, tùy chọn LLM local."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ..local_llm import LlamaCppClient
from ..storage import atomic_write_json, write_jsonl
from .schema import (
    CLEANER_LOGIC_VERSION,
    CLEANER_PROMPT_VERSION,
    QualitySegment,
    SegmentChange,
)

# Ký tự rác thường gặp từ ASR / subtitle
GARBAGE_CHARS_RE = re.compile(r"[\uFFFD\u200b\u00ad]")
MULTISPACE_RE = re.compile(r"[ \t]{2,}")
# Số / % / thuật ngữ trading — nếu đổi nội dung số thì flag, không đoán
NUMBER_RE = re.compile(r"\d+([.,]\d+)?%?")
TRADING_HINTS = (
    "long",
    "short",
    "stop loss",
    "take profit",
    "đòn bẩy",
    "leverage",
    "entry",
    "exit",
    "vốn",
    "lệnh",
    "pips",
    "btc",
    "eth",
    "usdt",
    "funding",
    "liquid",
    "margin",
    "rsi",
    "macd",
    "fib",
    "support",
    "resistance",
    "kháng cự",
    "hỗ trợ",
)


def _has_trading_context(text: str) -> bool:
    lower = text.lower()
    return any(hint in lower for hint in TRADING_HINTS) or bool(NUMBER_RE.search(text))


def _numbers_signature(text: str) -> tuple[str, ...]:
    return tuple(NUMBER_RE.findall(text))


def rule_clean_text(text: str) -> tuple[str, list[SegmentChange]]:
    """Sửa lỗi rõ ràng, không viết lại phong cách."""

    changes: list[SegmentChange] = []
    original = text
    cleaned = GARBAGE_CHARS_RE.sub("", text)
    cleaned = cleaned.replace("…", "...")
    cleaned = MULTISPACE_RE.sub(" ", cleaned)
    cleaned = cleaned.strip()

    if cleaned != original:
        changes.append(
            SegmentChange(
                segment_id="",
                segment_index=0,
                start=0.0,
                end=0.0,
                raw_text=original,
                ai_text=cleaned,
                change_type="garbage",
                reason="Loại ký tự rác / khoảng trắng thừa",
                confidence="high",
            )
        )

    # Gộp lặp cụm từ liền kề (subtitle hay lặp dòng)
    words = cleaned.split()
    if len(words) >= 4:
        half = len(words) // 2
        if words[:half] == words[half : half * 2]:
            deduped = " ".join(words[:half])
            if deduped != cleaned:
                changes.append(
                    SegmentChange(
                        segment_id="",
                        segment_index=0,
                        start=0.0,
                        end=0.0,
                        raw_text=cleaned,
                        ai_text=deduped,
                        change_type="duplicate",
                        reason="Bỏ cụm từ lặp liền kề",
                        confidence="high",
                    )
                )
                cleaned = deduped

    return cleaned, changes


def clean_segment(segment: QualitySegment) -> tuple[QualitySegment, list[SegmentChange]]:
    cleaned_text, patch_changes = rule_clean_text(segment.text)
    segment_changes: list[SegmentChange] = []
    for change in patch_changes:
        trading = _has_trading_context(segment.text) or _has_trading_context(cleaned_text)
        nums_changed = _numbers_signature(change.raw_text) != _numbers_signature(change.ai_text)
        confidence = "high"
        needs_relisten = False
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
        segment_changes.append(change)

    if cleaned_text == segment.text:
        return segment, segment_changes

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
    ), segment_changes


def build_cleaning_prompt(segment: QualitySegment, glossary_terms: list[str]) -> str:
    glossary_line = ", ".join(glossary_terms[:40]) if glossary_terms else "(chưa có)"
    return f"""Bạn là trợ lý sửa transcript tiếng Việt từ ASR/subtitle. CHỈ sửa lỗi kỹ thuật.

Quy tắc bắt buộc:
- Không tóm tắt, không thêm kiến thức ngoài, không đổi giọng nói / slang / filler thật.
- Chỉ sửa: ký tự rác, dấu câu, xuống dòng sai, lỗi ASR rõ ràng, lặp từ.
- Thuật ngữ trading/số liệu: nếu không chắc, GIỮ nguyên và ghi needs_review trong JSON.
- Thuật ngữ đã thấy trên kênh (tham khảo, không bịa): {glossary_line}

Trả về JSON thuần: {{"text":"...","changed":true/false,"reason":"...","confidence":"low|medium|high","needs_relisten":true/false}}

Đoạn gốc:
{segment.text}
"""


def llm_clean_segment(
    segment: QualitySegment,
    client: LlamaCppClient,
    glossary_terms: list[str],
) -> tuple[QualitySegment, list[SegmentChange]]:
    prompt = build_cleaning_prompt(segment, glossary_terms)
    raw_response = client.complete(prompt, max_tokens=400, temperature=0.0)
    try:
        start = raw_response.find("{")
        end = raw_response.rfind("}") + 1
        payload = json.loads(raw_response[start:end])
    except (json.JSONDecodeError, ValueError):
        return clean_segment(segment)

    new_text = str(payload.get("text") or segment.text).strip()
    if not new_text or new_text == segment.text:
        return segment, []

    confidence = str(payload.get("confidence") or "medium")
    needs_relisten = bool(payload.get("needs_relisten"))
    trading = _has_trading_context(segment.text) or _has_trading_context(new_text)
    if _numbers_signature(segment.text) != _numbers_signature(new_text):
        confidence = "low"
        needs_relisten = True

    change = SegmentChange(
        segment_id=segment.segment_id,
        segment_index=segment.segment_index,
        start=segment.start,
        end=segment.end,
        raw_text=segment.text,
        ai_text=new_text,
        change_type="llm_fix",
        reason=str(payload.get("reason") or "LLM đề xuất sửa"),
        confidence=confidence,
        needs_relisten=needs_relisten,
        trading_term_flag=trading,
    )
    updated = QualitySegment(
        segment_id=segment.segment_id,
        video_id=segment.video_id,
        title=segment.title,
        published_at=segment.published_at,
        start=segment.start,
        end=segment.end,
        text=new_text,
        video_url=segment.video_url,
        source_type=segment.source_type,
        source_path=segment.source_path,
        language=segment.language,
        segment_index=segment.segment_index,
    )
    return updated, [change]


def clean_all_segments(
    segments: list[QualitySegment],
    *,
    root: Path | None = None,
    engine: str = "conservative-refine",
    endpoint: str | None = None,
    glossary_terms: list[str] | None = None,
) -> tuple[list[QualitySegment], list[SegmentChange]]:
    """engine: conservative-refine | rule-only | asr-reprocess | llm (legacy)."""

    glossary = glossary_terms or []
    normalized_engine = (engine or "conservative-refine").strip().lower()

    if endpoint or normalized_engine == "llm":
        client = LlamaCppClient(endpoint) if endpoint else None
        if client is None:
            raise ValueError("engine=llm hoặc --endpoint cần URL llama.cpp; mặc định dùng conservative-refine.")
        cleaned_segments: list[QualitySegment] = []
        all_changes: list[SegmentChange] = []
        for segment in segments:
            updated, changes = llm_clean_segment(segment, client, glossary)
            if not changes:
                updated, changes = clean_segment(segment)
            cleaned_segments.append(updated)
            all_changes.extend(changes)
        return cleaned_segments, all_changes

    if normalized_engine in ("rule-only", "rules"):
        cleaned_segments = []
        all_changes = []
        for segment in segments:
            updated, changes = clean_segment(segment)
            cleaned_segments.append(updated)
            all_changes.extend(changes)
        return cleaned_segments, all_changes

    if normalized_engine in ("asr-reprocess", "asr_reprocess"):
        if root is None:
            raise ValueError("engine=asr-reprocess cần project root để đọc audio và model.")
        from .asr_segment_refine import refine_all_with_asr

        config = None
        try:
            from ..config import load_project_config

            config = load_project_config(root)
        except Exception:
            config = {}
        asr_opts = (config or {}).get("transcript_quality", {}).get("asr_reprocess") or {}
        return refine_all_with_asr(segments, root, glossary_terms=glossary, asr_options=asr_opts)

    if normalized_engine in ("conservative-refine", "refine", "default"):
        if root is None:
            raise ValueError("engine=conservative-refine cần project root cho confusion map.")
        from .cleaner_refine import refine_all_segments

        return refine_all_segments(segments, root=root, glossary_terms=glossary)

    raise ValueError(
        f"engine không hỗ trợ: {engine!r}. "
        "Dùng: conservative-refine, rule-only, asr-reprocess, llm (legacy)."
    )


def write_ai_cleaned(
    root: Path,
    video_id: str,
    segments: list[QualitySegment],
    changes: list[SegmentChange],
    *,
    raw_source_hash: str,
    raw_source_path: str,
    model_id: str,
) -> None:
    from .raw_layer import quality_dir

    out_dir = quality_dir(root, video_id)
    write_jsonl(out_dir / "ai_cleaned.jsonl", [segment.to_dict() for segment in segments], root)
    write_jsonl(out_dir / "change_log.jsonl", [change.to_dict() for change in changes], root)
    atomic_write_json(
        out_dir / "ai_cleaned.meta.json",
        {
            "video_id": video_id,
            "input_raw_hash": raw_source_hash,
            "raw_source_path": raw_source_path,
            "cleaner_logic_version": CLEANER_LOGIC_VERSION,
            "cleaner_prompt_version": CLEANER_PROMPT_VERSION,
            "model_id": model_id,
            "segment_count": len(segments),
            "change_count": len(changes),
            "suspicious_count": sum(1 for c in changes if c.confidence == "low" or c.needs_relisten),
        },
        root,
    )
