"""Build content/style knowledge chunks from analysis artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .config import load_project_config
from .paths import configure_local_environment, to_project_relative
from .schema import KnowledgeChunk, TranscriptSegment
from .storage import sha256_text, write_jsonl
from .transcripts import iter_normalized_segments
from .youtube_collect import load_latest_catalog


def chunk_transcript_segments(
    segments: Iterable[TranscriptSegment],
    pipeline_version: str,
    max_chars: int = 1200,
) -> list[KnowledgeChunk]:
    """Group timestamped transcript segments into content chunks."""

    chunks: list[KnowledgeChunk] = []
    current: list[TranscriptSegment] = []
    current_chars = 0

    def flush() -> None:
        nonlocal current, current_chars
        if not current:
            return
        text = " ".join(segment.text.strip() for segment in current if segment.text.strip())
        if not text:
            current = []
            current_chars = 0
            return
        first = current[0]
        last = current[-1]
        chunk_hash = sha256_text(
            "|".join(
                [
                    "content",
                    first.video_id,
                    str(first.start),
                    str(last.end),
                    text,
                    pipeline_version,
                ]
            )
        )
        chunks.append(
            KnowledgeChunk(
                chunk_id=f"content:{first.video_id}:{chunk_hash[:16]}",
                kind="content",
                video_id=first.video_id,
                title=first.title,
                published_at=first.published_at,
                start=first.start,
                end=last.end,
                text=text,
                source_type=first.source_type,
                source_path=first.source_path,
                pipeline_version=pipeline_version,
            )
        )
        current = []
        current_chars = 0

    for segment in segments:
        text_len = len(segment.text)
        if current and current_chars + text_len > max_chars:
            flush()
        current.append(segment)
        current_chars += text_len
    flush()
    return chunks


def iter_style_chunks(root: str | Path | None = None) -> Iterable[KnowledgeChunk]:
    """Read style observations produced by analyze-local.

    These chunks are intentionally separate from content chunks and must not be
    used as factual evidence.
    """

    root_path = Path(root or ".").resolve()
    config = load_project_config(root_path)
    style_dir = root_path / config["storage"]["analysis_dir"] / "extractions" / "style"
    if not style_dir.exists():
        return
    for path in sorted(style_dir.glob("*.jsonl")):
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                row = json.loads(line)
                yield KnowledgeChunk(
                    chunk_id=row["chunk_id"],
                    kind="style",
                    video_id=row.get("video_id", ""),
                    title=row.get("title", ""),
                    published_at=row.get("published_at", ""),
                    start=row.get("start"),
                    end=row.get("end"),
                    text=row.get("text", ""),
                    source_type=row.get("source_type", "style_extraction"),
                    source_path=row.get("source_path", path.as_posix()),
                    pipeline_version=row.get("pipeline_version", ""),
                )


def iter_content_note_chunks(root: str | Path | None = None) -> Iterable[KnowledgeChunk]:
    """Read content facts produced by analyze-local as factual chunks."""

    root_path = Path(root or ".").resolve()
    config = load_project_config(root_path)
    content_dir = root_path / config["storage"]["analysis_dir"] / "extractions" / "content"
    if not content_dir.exists():
        return
    for path in sorted(content_dir.glob("*.jsonl")):
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                row = json.loads(line)
                yield KnowledgeChunk(
                    chunk_id=row["chunk_id"],
                    kind="content",
                    video_id=row.get("video_id", ""),
                    title=row.get("title", ""),
                    published_at=row.get("published_at", ""),
                    start=row.get("start"),
                    end=row.get("end"),
                    text=row.get("text", ""),
                    source_type=row.get("source_type", "local_llm_content_extraction"),
                    source_path=row.get("source_path", path.as_posix()),
                    pipeline_version=row.get("pipeline_version", ""),
                )


def iter_ocr_chunks(root: str | Path | None = None) -> Iterable[KnowledgeChunk]:
    """Read OCR text from frame analysis as factual screen evidence."""

    root_path = Path(root or ".").resolve()
    config = load_project_config(root_path)
    ocr_dir = root_path / config["storage"]["analysis_dir"] / "ocr"
    if not ocr_dir.exists():
        return

    catalog = {entry["video_id"]: entry for entry in load_latest_catalog(root_path)}
    pipeline_version = config["pipeline"]["version"]
    for path in sorted(ocr_dir.glob("*/ocr.json")):
        video_id = path.parent.name
        entry = catalog.get(video_id, {})
        title = entry.get("title", video_id)
        published_at = entry.get("published_at") or ""
        rows = json.loads(path.read_text(encoding="utf-8"))
        for index, row in enumerate(rows):
            text = str(row.get("text") or "").strip()
            if len(text) < 3:
                continue
            timestamp = row.get("timestamp")
            chunk_hash = sha256_text(
                "|".join(
                    [
                        "ocr",
                        video_id,
                        str(timestamp),
                        text,
                        pipeline_version,
                    ]
                )
            )
            yield KnowledgeChunk(
                chunk_id=f"ocr:{video_id}:{index}:{chunk_hash[:16]}",
                kind="content",
                video_id=video_id,
                title=title,
                published_at=published_at,
                start=float(timestamp) if timestamp is not None else None,
                end=float(timestamp) if timestamp is not None else None,
                text=f"OCR màn hình: {text}",
                source_type=str(row.get("source_type") or "ocr_paddleocr"),
                source_path=to_project_relative(path, root_path),
                pipeline_version=pipeline_version,
            )


def build_knowledge_chunks(root: str | Path | None = None) -> list[KnowledgeChunk]:
    root_path = Path(root or ".").resolve()
    configure_local_environment(root_path)
    config = load_project_config(root_path)
    pipeline_version = config["pipeline"]["version"]
    content_chunks = chunk_transcript_segments(iter_normalized_segments(root_path), pipeline_version)
    chunks = [
        *content_chunks,
        *list(iter_ocr_chunks(root_path)),
        *list(iter_content_note_chunks(root_path)),
        *list(iter_style_chunks(root_path)),
    ]

    output_path = root_path / config["storage"]["analysis_dir"] / "chunks.jsonl"
    write_jsonl(output_path, [chunk.to_dict() for chunk in chunks], root_path)
    return chunks
