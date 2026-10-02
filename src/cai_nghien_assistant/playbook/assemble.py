"""Join a video's full transcript into one source file. Do not cut sentences."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from ..config import load_project_config
from ..knowledge import iter_ocr_chunks, iter_segments_for_index
from ..paths import configure_local_environment, to_project_relative
from ..retrieval import format_timestamp
from ..schema import TranscriptSegment
from ..speech_units import sentence_spans
from ..storage import atomic_write_json, atomic_write_text
from .paths import knowledge_root, video_dir


def render_source_markdown(
    *,
    video_id: str,
    title: str,
    published_at: str,
    source_type: str,
    segments: list[TranscriptSegment],
    ocr_lines: list[str] | None = None,
) -> str:
    ordered = sorted(segments, key=lambda item: (item.start, item.end))
    lines = [
        f"# {title}",
        "",
        f"- video_id: {video_id}",
        f"- published_at: {published_at}",
        f"- source_type: {source_type}",
        "",
        "## Lời thoại",
        "",
    ]
    for segment in sentence_spans(ordered):
        text = segment.text.strip()
        if not text:
            continue
        stamp = format_timestamp(segment.start)
        lines.append(f"[{stamp}] {text}")
        lines.append("")

    ocr_lines = ocr_lines or []
    if ocr_lines:
        lines.append("## Chữ trên màn hình (OCR)")
        lines.append("")
        for line in ocr_lines:
            cleaned = line.strip()
            if cleaned:
                lines.append(f"- {cleaned}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _group_segments(root: Path) -> dict[str, list[TranscriptSegment]]:
    grouped: dict[str, list[TranscriptSegment]] = defaultdict(list)
    for segment in iter_segments_for_index(root):
        if segment.video_id:
            grouped[segment.video_id].append(segment)
    return grouped


def _ocr_lines_by_video(root: Path) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for chunk in iter_ocr_chunks(root):
        text = chunk.text.removeprefix("OCR màn hình: ").strip()
        if not text:
            continue
        stamp = format_timestamp(chunk.start)
        grouped[chunk.video_id].append(f"{stamp} {text}".strip())
    return grouped


def assemble_video_sources(
    root: str | Path | None = None,
    *,
    limit: int | None = None,
    force: bool = False,
) -> dict[str, Any]:
    root_path = Path(root or ".").resolve()
    configure_local_environment(root_path)
    grouped = _group_segments(root_path)
    ocr_by_video = _ocr_lines_by_video(root_path)
    video_ids = sorted(grouped.keys())
    if limit:
        video_ids = video_ids[:limit]

    written = 0
    skipped = 0
    for video_id in video_ids:
        segments = grouped[video_id]
        if not segments:
            continue
        first = sorted(segments, key=lambda item: item.start)[0]
        out_dir = video_dir(root_path, video_id)
        out_path = out_dir / "source.md"
        if out_path.exists() and not force:
            skipped += 1
            continue
        markdown = render_source_markdown(
            video_id=video_id,
            title=first.title,
            published_at=first.published_at,
            source_type=first.source_type,
            segments=segments,
            ocr_lines=ocr_by_video.get(video_id, []),
        )
        atomic_write_text(out_path, markdown, root_path)
        written += 1

    manifest = {
        "videos_seen": len(grouped),
        "videos_written": written,
        "videos_skipped": skipped,
        "knowledge_root": to_project_relative(knowledge_root(root_path), root_path),
        "pipeline_version": load_project_config(root_path)["pipeline"]["version"],
    }
    atomic_write_json(knowledge_root(root_path) / "assemble_manifest.json", manifest, root_path)
    return manifest
