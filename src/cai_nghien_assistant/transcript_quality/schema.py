"""Kiểu dữ liệu cho pipeline chất lượng transcript."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

# Phiên bản logic làm sạch rule-based / prompt — đổi khi đổi thuật toán.
CLEANER_LOGIC_VERSION = "2.0.0"
CLEANER_PROMPT_VERSION = "1"


@dataclass
class QualitySegment:
    """Một đoạn transcript có timestamp và link video."""

    segment_id: str
    video_id: str
    title: str
    published_at: str
    start: float
    end: float
    text: str
    video_url: str
    source_type: str
    source_path: str
    language: str | None = None
    segment_index: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SegmentChange:
    """Một thay đổi do AI đề xuất — dùng review và audit."""

    segment_id: str
    segment_index: int
    start: float
    end: float
    raw_text: str
    ai_text: str
    change_type: str
    reason: str
    confidence: str  # low | medium | high — mức rủi ro nếu áp dụng
    needs_relisten: bool = False
    trading_term_flag: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReviewState:
    video_id: str
    status: str  # pending_ai | ai_done_unreviewed | in_review | approved | has_suspicious
    title: str = ""
    published_at: str = ""
    raw_source_hash: str = ""
    raw_source_path: str = ""
    ai_input_hash: str = ""
    cleaner_logic_version: str = ""
    model_id: str = ""
    suspicious_count: int = 0
    accepted_low_risk: bool = False
    approved_at: str | None = None
    partial_accepted_segment_ids: list[str] = field(default_factory=list)
    rejected_change_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def make_segment_id(video_id: str, segment_index: int, start: float) -> str:
    return f"{video_id}:{segment_index}:{start:.3f}"
