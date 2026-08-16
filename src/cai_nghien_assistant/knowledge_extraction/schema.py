"""Structured knowledge records with full provenance."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class KnowledgeFact:
    fact_id: str
    video_id: str
    title: str
    published_at: str
    start: float | None
    end: float | None
    fact_text: str
    evidence_quote: str
    category: str
    source_type: str
    source_path: str
    pipeline_version: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
