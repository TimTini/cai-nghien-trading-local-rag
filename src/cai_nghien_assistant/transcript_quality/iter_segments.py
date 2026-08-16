"""Đọc segment cho index/RAG — ưu tiên approved, fallback AI (provisional)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from ..config import load_project_config
from ..schema import TranscriptSegment
from ..transcripts import catalog_video_order
from .raw_layer import quality_dir


def _rows_to_transcript_segments(
    rows: list[dict],
    *,
    source_type: str,
    source_path: str,
) -> Iterable[TranscriptSegment]:
    for row in rows:
        yield TranscriptSegment(
            video_id=str(row.get("video_id") or ""),
            title=str(row.get("title") or ""),
            published_at=str(row.get("published_at") or ""),
            start=float(row.get("start") or 0),
            end=float(row.get("end") or 0),
            text=str(row.get("text") or ""),
            source_type=source_type,
            source_path=source_path,
            language=row.get("language"),
            confidence=row.get("confidence"),
        )


def iter_quality_segments(root: Path) -> Iterable[TranscriptSegment]:
    """Approved nếu video đã duyệt; không thì AI cleaned (gắn nhãn provisional)."""

    config = load_project_config(root)
    tq_root = root / config["storage"]["analysis_dir"] / "transcript_quality"
    if not tq_root.exists():
        return

    available = {path.name for path in tq_root.iterdir() if path.is_dir()}
    ordered = [vid for vid in catalog_video_order(root) if vid in available]
    ordered.extend(sorted(available - set(ordered)))

    for video_id in ordered:
        out_dir = quality_dir(root, video_id)
        state_path = out_dir / "review_state.json"
        approved_path = out_dir / "approved.jsonl"
        ai_path = out_dir / "ai_cleaned.jsonl"

        if state_path.exists():
            state = json.loads(state_path.read_text(encoding="utf-8"))
            if state.get("status") == "approved" and approved_path.exists():
                rows = [
                    json.loads(line)
                    for line in approved_path.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
                rel = f"data/analysis/transcript_quality/{video_id}/approved.jsonl"
                yield from _rows_to_transcript_segments(
                    rows,
                    source_type="transcript_approved",
                    source_path=rel,
                )
                continue

        if ai_path.exists():
            rows = [
                json.loads(line)
                for line in ai_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            rel = f"data/analysis/transcript_quality/{video_id}/ai_cleaned.jsonl"
            yield from _rows_to_transcript_segments(
                rows,
                source_type="transcript_ai_provisional",
                source_path=rel,
            )
