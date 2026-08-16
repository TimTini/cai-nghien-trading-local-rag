"""Tạo lớp raw bất biến từ transcript đã normalize (youtube/asr)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..config import load_project_config
from ..paths import configure_local_environment, to_project_relative
from ..storage import atomic_write_json, read_jsonl, sha256_file, write_jsonl_once
from ..transcripts import catalog_video_order
from .schema import QualitySegment, make_segment_id


def quality_dir(root: Path, video_id: str) -> Path:
    config = load_project_config(root)
    path = root / config["storage"]["analysis_dir"] / "transcript_quality" / video_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def pick_normalized_source(transcript_dir: Path) -> Path | None:
    """Ưu tiên ASR local, sau đó subtitle YouTube."""
    for name in ("asr_faster_whisper.jsonl", "youtube.jsonl", "selected.jsonl"):
        candidate = transcript_dir / name
        if candidate.exists():
            return candidate
    jsonl_files = sorted(transcript_dir.glob("*.jsonl"))
    return jsonl_files[0] if jsonl_files else None


def _load_manifest_url(raw_video_dir: Path, video_id: str) -> str:
    manifest_path = raw_video_dir / "manifest.json"
    if manifest_path.exists():
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        return str(data.get("url") or f"https://www.youtube.com/watch?v={video_id}")
    return f"https://www.youtube.com/watch?v={video_id}"


def rows_to_quality_segments(
    rows: list[dict[str, Any]],
    video_url: str,
) -> list[QualitySegment]:
    segments: list[QualitySegment] = []
    for index, row in enumerate(rows):
        video_id = str(row.get("video_id") or "")
        start = float(row.get("start") or 0)
        end = float(row.get("end") or start)
        text = str(row.get("text") or "").strip()
        if not text:
            continue
        segments.append(
            QualitySegment(
                segment_id=make_segment_id(video_id, index, start),
                video_id=video_id,
                title=str(row.get("title") or ""),
                published_at=str(row.get("published_at") or ""),
                start=start,
                end=end,
                text=text,
                video_url=video_url,
                source_type=str(row.get("source_type") or "normalized"),
                source_path=str(row.get("source_path") or ""),
                language=row.get("language"),
                segment_index=index,
            )
        )
    return segments


def ensure_raw_layer(root: Path, video_id: str) -> tuple[list[QualitySegment], str, str]:
    """Ghi raw.jsonl một lần; không ghi đè nếu nguồn normalize không đổi."""

    configure_local_environment(root)
    config = load_project_config(root)
    transcript_dir = root / config["storage"]["analysis_dir"] / "transcripts" / video_id
    source_path = pick_normalized_source(transcript_dir)
    if source_path is None:
        return [], "", ""

    source_hash = sha256_file(source_path)
    out_dir = quality_dir(root, video_id)
    meta_path = out_dir / "raw.meta.json"
    raw_path = out_dir / f"raw_{source_hash[:8]}.jsonl"

    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("source_hash") == source_hash:
            existing_raw = out_dir / Path(str(meta.get("raw_file") or "raw.jsonl"))
            if existing_raw.exists():
                rows = read_jsonl(existing_raw)
                return (
                    rows_to_quality_segments(rows, str(meta.get("video_url") or "")),
                    source_hash,
                    to_project_relative(source_path, root),
                )

    raw_video_dir = root / config["storage"]["raw_dir"] / "videos" / video_id
    video_url = _load_manifest_url(raw_video_dir, video_id)
    normalized_rows = read_jsonl(source_path)
    segments = rows_to_quality_segments(normalized_rows, video_url)
    payload = [segment.to_dict() for segment in segments]
    write_jsonl_once(raw_path, payload, root)
    atomic_write_json(
        meta_path,
        {
            "video_id": video_id,
            "raw_file": raw_path.name,
            "source_path": to_project_relative(source_path, root),
            "source_hash": source_hash,
            "source_type": segments[0].source_type if segments else "unknown",
            "segment_count": len(segments),
            "video_url": video_url,
        },
        root,
    )
    return segments, source_hash, to_project_relative(source_path, root)


def ordered_video_ids_with_transcripts(root: Path, content_type: str | None = None) -> list[str]:
    config = load_project_config(root)
    transcripts_root = root / config["storage"]["analysis_dir"] / "transcripts"
    if not transcripts_root.exists():
        return []
    available = []
    for path in transcripts_root.iterdir():
        if path.is_dir() and pick_normalized_source(path):
            available.append(path.name)
    catalog_order = catalog_video_order(root)
    ordered = [vid for vid in catalog_order if vid in available]
    ordered.extend(sorted(set(available) - set(ordered)))
    if not content_type:
        return ordered
    catalog_path = root / config["storage"]["analysis_dir"] / "state" / "latest_catalog.jsonl"
    if not catalog_path.exists():
        return ordered
    allowed = set()
    for line in catalog_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("content_type") == content_type and row.get("video_id"):
            allowed.add(row["video_id"])
    return [vid for vid in ordered if vid in allowed]
