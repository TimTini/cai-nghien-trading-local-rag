"""Transcript normalization.

Raw subtitle files stay untouched in data/raw. Normalized transcript segments
are written to data/analysis with provenance back to the raw file.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any, Iterable

from .config import load_project_config
from .paths import configure_local_environment, to_project_relative
from .schema import TranscriptSegment
from .storage import atomic_write_json, write_jsonl


TIMESTAMP_RE = re.compile(
    r"(?P<start>\d\d:\d\d:\d\d(?:[.,]\d+)?)\s+-->\s+(?P<end>\d\d:\d\d:\d\d(?:[.,]\d+)?)"
)
TAG_RE = re.compile(r"<[^>]+>")


def parse_timestamp(value: str) -> float:
    hours, minutes, seconds = value.replace(",", ".").split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def clean_subtitle_text(text: str) -> str:
    text = TAG_RE.sub("", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _clean_vtt_line(line: str) -> str:
    return clean_subtitle_text(line)


def parse_vtt(path: str | Path) -> list[tuple[float, float, str]]:
    cues: list[tuple[float, float, str]] = []
    lines = Path(path).read_text(encoding="utf-8", errors="ignore").splitlines()
    idx = 0
    previous_text = ""
    while idx < len(lines):
        match = TIMESTAMP_RE.search(lines[idx])
        if not match:
            idx += 1
            continue
        start = parse_timestamp(match.group("start"))
        end = parse_timestamp(match.group("end"))
        idx += 1
        text_lines: list[str] = []
        while idx < len(lines) and lines[idx].strip():
            cleaned = _clean_vtt_line(lines[idx])
            if cleaned:
                text_lines.append(cleaned)
            idx += 1
        while text_lines and text_lines[0] == previous_text:
            text_lines.pop(0)
        text = clean_subtitle_text(" ".join(text_lines))
        if text == previous_text:
            text = ""
        if text:
            cues.append((start, end, text))
            previous_text = text
        idx += 1
    return cues


def parse_json3(path: str | Path) -> list[tuple[float, float, str]]:
    data = json.loads(Path(path).read_text(encoding="utf-8", errors="ignore"))
    cues: list[tuple[float, float, str]] = []
    for event in data.get("events", []):
        segments = event.get("segs") or []
        text = clean_subtitle_text("".join(segment.get("utf8", "") for segment in segments))
        if not text:
            continue
        start = float(event.get("tStartMs", 0)) / 1000.0
        duration = float(event.get("dDurationMs", 0)) / 1000.0
        cues.append((start, start + duration, text))
    return cues


def subtitle_priority(path: Path) -> tuple[int, str]:
    name = path.name.lower()
    if ".vi" in name:
        language_rank = 0
    elif ".en" in name:
        language_rank = 1
    else:
        language_rank = 2
    format_rank = 0 if path.suffix.lower() == ".vtt" else 1
    return (language_rank + format_rank, name)


def subtitle_language(path: Path) -> str | None:
    name = path.name.lower()
    if ".vi" in name:
        return "vi"
    if ".en" in name:
        return "en"
    return None


def find_subtitle_files(video_dir: Path) -> list[Path]:
    candidates = [
        path
        for path in video_dir.iterdir()
        if path.is_file() and path.suffix.lower() in {".vtt", ".json3", ".srv3"}
    ]
    return sorted(candidates, key=subtitle_priority)


def has_sidecar_payload(video_dir: Path) -> bool:
    return (video_dir / "manifest.json").exists() or bool(find_subtitle_files(video_dir))


def _load_manifest(video_dir: Path) -> dict[str, Any]:
    manifest_path = video_dir / "manifest.json"
    if manifest_path.exists():
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    info_files = sorted(video_dir.glob("*.info.json"))
    if info_files:
        info = json.loads(info_files[0].read_text(encoding="utf-8", errors="ignore"))
        return {
            "video_id": info.get("id") or video_dir.name,
            "title": info.get("title") or "",
            "published_at": str(info.get("upload_date") or "")[:10],
            "url": info.get("webpage_url") or "",
            "content_type": "",
        }
    return {"video_id": video_dir.name, "title": "", "published_at": "", "url": "", "content_type": ""}


def _segments_from_file(path: Path) -> list[tuple[float, float, str]]:
    if path.suffix.lower() == ".vtt":
        return parse_vtt(path)
    if path.suffix.lower() in {".json3", ".srv3"}:
        return parse_json3(path)
    return []


def normalize_video_transcript(root: str | Path | None, video_id: str) -> int:
    root_path = Path(root or ".").resolve()
    configure_local_environment(root_path)
    config = load_project_config(root_path)
    raw_video_dir = root_path / config["storage"]["raw_dir"] / "videos" / video_id
    output_dir = root_path / config["storage"]["analysis_dir"] / "transcripts" / video_id
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = _load_manifest(raw_video_dir)
    subtitle_files = find_subtitle_files(raw_video_dir) if raw_video_dir.exists() else []
    if not subtitle_files:
        atomic_write_json(
            output_dir / "needs_asr.json",
            {
                "video_id": video_id,
                "reason": "No usable YouTube subtitle sidecar found.",
                "next_step": "Download audio legally if needed, then run a local ASR task such as faster-whisper.",
            },
            root_path,
        )
        return 0

    source_file = subtitle_files[0]
    parsed = _segments_from_file(source_file)
    rows = [
        TranscriptSegment(
            video_id=manifest.get("video_id") or video_id,
            title=manifest.get("title") or "",
            published_at=manifest.get("published_at") or "",
            start=start,
            end=end,
            text=text,
            source_type="youtube_subtitle",
            source_path=to_project_relative(source_file, root_path),
            language=subtitle_language(source_file),
        ).to_dict()
        for start, end, text in parsed
    ]
    write_jsonl(output_dir / "youtube.jsonl", rows, root_path)
    return len(rows)


def catalog_video_order(root: str | Path | None = None) -> list[str]:
    root_path = Path(root or ".").resolve()
    config = load_project_config(root_path)
    catalog_path = root_path / config["storage"]["analysis_dir"] / "state" / "latest_catalog.jsonl"
    if not catalog_path.exists():
        return []
    rows = [json.loads(line) for line in catalog_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows.sort(key=lambda item: (item.get("published_at") or "9999-99-99", item.get("video_id") or ""))
    return [row["video_id"] for row in rows if row.get("video_id")]


def normalize_all_transcripts(
    root: str | Path | None = None,
    limit: int | None = None,
    content_type: str | None = None,
) -> dict[str, int]:
    root_path = Path(root or ".").resolve()
    configure_local_environment(root_path)
    config = load_project_config(root_path)
    videos_dir = root_path / config["storage"]["raw_dir"] / "videos"
    result: dict[str, int] = {}
    if not videos_dir.exists():
        return result
    available = {path.name for path in videos_dir.iterdir() if path.is_dir() and has_sidecar_payload(path)}
    catalog_path = root_path / config["storage"]["analysis_dir"] / "state" / "latest_catalog.jsonl"
    catalog_rows = []
    if catalog_path.exists():
        catalog_rows = [json.loads(line) for line in catalog_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        catalog_rows.sort(key=lambda item: (item.get("published_at") or "9999-99-99", item.get("video_id") or ""))
    if content_type:
        catalog_rows = [row for row in catalog_rows if row.get("content_type") == content_type]
    ordered = [row["video_id"] for row in catalog_rows if row.get("video_id") in available]
    ordered.extend(sorted(available - set(ordered)))
    if limit:
        ordered = ordered[:limit]
    for video_id in ordered:
        result[video_id] = normalize_video_transcript(root_path, video_id)
    return result


def iter_normalized_segments(root: str | Path | None = None) -> Iterable[TranscriptSegment]:
    root_path = Path(root or ".").resolve()
    config = load_project_config(root_path)
    transcripts_dir = root_path / config["storage"]["analysis_dir"] / "transcripts"
    if not transcripts_dir.exists():
        return
    for jsonl_path in sorted(transcripts_dir.glob("*/youtube.jsonl")):
        with jsonl_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                yield TranscriptSegment(**json.loads(line))
