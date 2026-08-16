"""Playbook records: one complete rule, never a cut sentence."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class PlaybookRule:
    rule_id: str
    text: str
    conditions: list[str]
    exceptions: list[str]
    start: float | None
    end: float | None
    evidence_quote: str
    kind: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(row: dict[str, Any]) -> PlaybookRule:
        return PlaybookRule(
            rule_id=str(row.get("rule_id") or ""),
            text=str(row.get("text") or ""),
            conditions=[str(item) for item in (row.get("conditions") or [])],
            exceptions=[str(item) for item in (row.get("exceptions") or [])],
            start=row.get("start"),
            end=row.get("end"),
            evidence_quote=str(row.get("evidence_quote") or ""),
            kind=str(row.get("kind") or "doctrine"),
        )


@dataclass(frozen=True)
class VideoArticle:
    video_id: str
    title: str
    published_at: str
    source_type: str
    thesis: str
    rules: list[PlaybookRule]
    topics: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "video_id": self.video_id,
            "title": self.title,
            "published_at": self.published_at,
            "source_type": self.source_type,
            "thesis": self.thesis,
            "rules": [rule.to_dict() for rule in self.rules],
            "topics": list(self.topics),
        }

    @staticmethod
    def from_dict(row: dict[str, Any]) -> VideoArticle:
        rules = [PlaybookRule.from_dict(item) for item in (row.get("rules") or [])]
        return VideoArticle(
            video_id=str(row.get("video_id") or ""),
            title=str(row.get("title") or ""),
            published_at=str(row.get("published_at") or ""),
            source_type=str(row.get("source_type") or ""),
            thesis=str(row.get("thesis") or ""),
            rules=rules,
            topics=[str(item) for item in (row.get("topics") or [])],
        )


@dataclass(frozen=True)
class Chapter:
    topic_id: str
    title: str
    keywords: list[str]
    path: str
    body: str = field(default="")
