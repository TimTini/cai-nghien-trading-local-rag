"""Small typed records used across the pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class TranscriptSegment:
    video_id: str
    title: str
    published_at: str
    start: float
    end: float
    text: str
    source_type: str
    source_path: str
    language: str | None = None
    confidence: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class KnowledgeChunk:
    chunk_id: str
    kind: str
    video_id: str
    title: str
    published_at: str
    start: float | None
    end: float | None
    text: str
    source_type: str
    source_path: str
    pipeline_version: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Evidence:
    chunk_id: str
    kind: str
    video_id: str
    title: str
    published_at: str
    start: float | None
    end: float | None
    text: str
    source_type: str
    source_path: str
    score: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

