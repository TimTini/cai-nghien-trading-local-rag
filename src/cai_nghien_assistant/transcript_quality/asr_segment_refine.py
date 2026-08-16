"""Transcribe lại clip audio cho đoạn heuristic xấu — faster-whisper, không LLM chat."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from ..config import load_project_config
from ..media import first_media_file
from .cleaner_refine import refine_segment
from .metrics import segment_needs_asr_retry, segment_quality_score
from .schema import QualitySegment, SegmentChange


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _extract_audio_clip(
    audio_path: Path,
    start: float,
    end: float,
    out_wav: Path,
) -> bool:
    duration = max(0.5, end - start)
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        str(max(0.0, start)),
        "-i",
        str(audio_path),
        "-t",
        str(duration),
        "-ac",
        "1",
        "-ar",
        "16000",
        str(out_wav),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
        return proc.returncode == 0 and out_wav.exists() and out_wav.stat().st_size > 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _transcribe_clip(
    root: Path,
    wav_path: Path,
    *,
    model_size: str,
    device: str,
    compute_type: str,
    beam_size: int,
) -> str:
    from ..asr import _import_faster_whisper

    config = load_project_config(root)
    WhisperModel = _import_faster_whisper()
    model_download_root = root / config["models"]["asr_model_dir"] / "faster-whisper"
    model = WhisperModel(
        model_size,
        device=device,
        compute_type=compute_type,
        download_root=str(model_download_root),
    )
    segments, _info = model.transcribe(
        str(wav_path),
        language="vi",
        task="transcribe",
        beam_size=beam_size,
        vad_filter=False,
        condition_on_previous_text=False,
    )
    parts = [str(seg.text).strip() for seg in segments if str(seg.text).strip()]
    return " ".join(parts).strip()


def _accept_asr_rewrite(original: str, candidate: str) -> bool:
    if not candidate or candidate == original:
        return False
    orig_score = segment_quality_score(original)
    new_score = segment_quality_score(candidate)
    if new_score["garbage_chars"] > orig_score["garbage_chars"]:
        return False
    if new_score["readable_sentence_ratio"] < orig_score["readable_sentence_ratio"] - 0.15:
        return False
    # Không chấp nhận đoạn quá ngắn hoặc quá dài so với gốc (tránh viết lại)
    if len(candidate) < len(original) * 0.5 or len(candidate) > len(original) * 1.35:
        return False
    return True


def refine_segment_with_asr(
    segment: QualitySegment,
    root: Path,
    *,
    glossary_terms: list[str],
    model_size: str = "large-v3",
    device: str = "cuda",
    compute_type: str = "float16",
    beam_size: int = 8,
) -> tuple[QualitySegment, list[SegmentChange]]:
    """Rule/glossary trước; nếu đoạn xấu và có audio thì thử clip ASR."""

    updated, changes = refine_segment(segment, root=root, glossary_terms=glossary_terms)
    if not segment_needs_asr_retry(updated.text):
        return updated, changes

    audio_path = first_media_file(root, segment.video_id, "audio")
    if audio_path is None or not _ffmpeg_available():
        return updated, changes

    with tempfile.TemporaryDirectory(prefix="cnga_asr_refine_") as tmp:
        wav_path = Path(tmp) / "clip.wav"
        if not _extract_audio_clip(audio_path, segment.start, segment.end, wav_path):
            return updated, changes
        try:
            new_text = _transcribe_clip(
                root,
                wav_path,
                model_size=model_size,
                device=device,
                compute_type=compute_type,
                beam_size=beam_size,
            )
        except RuntimeError:
            return updated, changes

    if not _accept_asr_rewrite(updated.text, new_text):
        return updated, changes

    asr_change = SegmentChange(
        segment_id=segment.segment_id,
        segment_index=segment.segment_index,
        start=segment.start,
        end=segment.end,
        raw_text=updated.text,
        ai_text=new_text,
        change_type="asr_reclip",
        reason="Transcribe lại clip audio (faster-whisper, beam cao)",
        confidence="medium",
        needs_relisten=True,
        trading_term_flag=False,
    )
    asr_segment = QualitySegment(
        segment_id=updated.segment_id,
        video_id=updated.video_id,
        title=updated.title,
        published_at=updated.published_at,
        start=updated.start,
        end=updated.end,
        text=new_text,
        video_url=updated.video_url,
        source_type=updated.source_type,
        source_path=updated.source_path,
        language=updated.language,
        segment_index=updated.segment_index,
    )
    return asr_segment, changes + [asr_change]


def refine_all_with_asr(
    segments: list[QualitySegment],
    root: Path,
    *,
    glossary_terms: list[str] | None = None,
    asr_options: dict[str, Any] | None = None,
) -> tuple[list[QualitySegment], list[SegmentChange]]:
    opts = asr_options or {}
    glossary = glossary_terms or []
    out_segments: list[QualitySegment] = []
    all_changes: list[SegmentChange] = []
    for segment in segments:
        updated, changes = refine_segment_with_asr(
            segment,
            root,
            glossary_terms=glossary,
            model_size=str(opts.get("model_size") or "large-v3"),
            device=str(opts.get("device") or "cuda"),
            compute_type=str(opts.get("compute_type") or "float16"),
            beam_size=int(opts.get("beam_size") or 8),
        )
        out_segments.append(updated)
        all_changes.extend(changes)
    return out_segments, all_changes
