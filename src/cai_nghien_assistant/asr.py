"""Local ASR pipeline for project-owned audio files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import load_project_config
from .media import first_media_file, select_catalog_entries
from .paths import configure_local_environment, to_project_relative
from .schema import TranscriptSegment
from .storage import atomic_write_json, write_jsonl


def _import_faster_whisper():
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("Missing faster-whisper. Install with: uv sync --extra youtube --extra asr --extra dev") from exc
    return WhisperModel


def transcribe_faster_whisper(
    root: str | Path | None,
    video_id: str,
    model_size: str = "large-v3",
    device: str = "cuda",
    compute_type: str = "float16",
    beam_size: int = 5,
    vad_filter: bool = False,
    force: bool = False,
) -> int:
    root_path = Path(root or ".").resolve()
    configure_local_environment(root_path)
    config = load_project_config(root_path)
    audio_path = first_media_file(root_path, video_id, "audio")
    if not audio_path:
        raise RuntimeError(f"No audio manifest/file for video {video_id}. Run fetch-audio first.")

    output_dir = root_path / config["storage"]["analysis_dir"] / "transcripts" / video_id
    output_path = output_dir / "asr_faster_whisper.jsonl"
    metadata_path = output_dir / "asr_faster_whisper.meta.json"
    if output_path.exists() and not force:
        return sum(1 for _ in output_path.open("r", encoding="utf-8"))

    WhisperModel = _import_faster_whisper()
    model_download_root = root_path / config["models"]["asr_model_dir"] / "faster-whisper"
    model = WhisperModel(
        model_size,
        device=device,
        compute_type=compute_type,
        download_root=str(model_download_root),
    )
    segments, info = model.transcribe(
        str(audio_path),
        language="vi",
        task="transcribe",
        beam_size=beam_size,
        vad_filter=vad_filter,
        vad_parameters={"min_silence_duration_ms": 500} if vad_filter else None,
    )

    catalog = {entry["video_id"]: entry for entry in select_catalog_entries(root_path)}
    entry = catalog.get(video_id, {})
    rows: list[dict[str, Any]] = []
    for segment in segments:
        rows.append(
            TranscriptSegment(
                video_id=video_id,
                title=entry.get("title", ""),
                published_at=entry.get("published_at", ""),
                start=float(segment.start),
                end=float(segment.end),
                text=str(segment.text).strip(),
                source_type="asr_faster_whisper",
                source_path=to_project_relative(audio_path, root_path),
                language=getattr(info, "language", "vi"),
                confidence=None,
            ).to_dict()
        )
    write_jsonl(output_path, rows, root_path)
    atomic_write_json(
        metadata_path,
        {
            "video_id": video_id,
            "engine": "faster-whisper",
            "model_size": model_size,
            "device": device,
            "compute_type": compute_type,
            "beam_size": beam_size,
            "vad_filter": vad_filter,
            "audio_path": to_project_relative(audio_path, root_path),
            "detected_language": getattr(info, "language", None),
            "language_probability": getattr(info, "language_probability", None),
            "duration": getattr(info, "duration", None),
            "segments": len(rows),
        },
        root_path,
    )
    return len(rows)


def asr_batch(
    root: str | Path | None = None,
    limit: int | None = None,
    content_type: str | None = None,
    offset: int = 0,
    model_size: str = "large-v3",
    device: str = "cuda",
    compute_type: str = "float16",
    beam_size: int = 5,
    vad_filter: bool = False,
    force: bool = False,
) -> dict[str, int]:
    root_path = Path(root or ".").resolve()
    entries = select_catalog_entries(root_path, limit=limit, content_type=content_type, offset=offset)
    result: dict[str, int] = {}
    for index, entry in enumerate(entries, start=1):
        video_id = entry["video_id"]
        if not first_media_file(root_path, video_id, "audio"):
            continue
        print(f"[asr] {index}/{len(entries)} {entry.get('published_at') or 'unknown'} {video_id} {entry.get('title', '')}")
        result[video_id] = transcribe_faster_whisper(
            root_path,
            video_id,
            model_size=model_size,
            device=device,
            compute_type=compute_type,
            beam_size=beam_size,
            vad_filter=vad_filter,
            force=force,
        )
    return result
