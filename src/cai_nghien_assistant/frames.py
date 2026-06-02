"""Candidate frame extraction and OCR helpers.

This module keeps vision work sparse: detect candidate frames by code first,
then run OCR/local vision only on selected timestamps.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from .config import load_project_config
from .media import first_media_file, select_catalog_entries
from .paths import configure_local_environment, to_project_relative
from .storage import atomic_write_json


PTS_RE = re.compile(r"pts_time:(?P<time>[0-9.]+)")


def extract_candidate_frames(
    root: str | Path | None,
    video_id: str,
    media_path: str | Path,
    scene_threshold: float = 0.35,
    max_frames: int = 80,
    force: bool = False,
) -> list[dict[str, object]]:
    """Use ffmpeg scene detection to extract sparse frames.

    Requires ffmpeg on PATH. The media must already be legally present inside
    data/raw.
    """

    root_path = Path(root or ".").resolve()
    configure_local_environment(root_path)
    config = load_project_config(root_path)
    media = Path(media_path).resolve()
    if root_path not in media.parents:
        raise ValueError("media_path must be inside the project")

    output_dir = root_path / config["storage"]["analysis_dir"] / "frames" / video_id
    manifest_path = output_dir / "frames.json"
    if manifest_path.exists() and not force:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True, exist_ok=True)
    pattern = output_dir / "scene-%05d.jpg"
    command = [
        "ffmpeg",
        "-y" if force else "-n",
        "-hide_banner",
        "-i",
        str(media),
        "-vf",
        f"select='gt(scene,{scene_threshold})',scale=1280:-1,showinfo",
        "-vsync",
        "vfr",
        "-frames:v",
        str(max_frames),
        str(pattern),
    ]
    completed = subprocess.run(command, check=False, text=True, capture_output=True)
    timestamps = [float(match.group("time")) for match in PTS_RE.finditer(completed.stderr)]
    frame_files = sorted(output_dir.glob("scene-*.jpg"))
    no_scene_frames = "No filtered frames" in completed.stderr or "Nothing was written into output file" in completed.stderr
    if completed.returncode not in {0, 1} and not frame_files and not no_scene_frames:
        raise RuntimeError(completed.stderr[-2000:])
    if not frame_files:
        fallback = output_dir / "fallback-00001.jpg"
        subprocess.run(
            [
                "ffmpeg",
                "-y" if force else "-n",
                "-hide_banner",
                "-ss",
                "1",
                "-i",
                str(media),
                "-frames:v",
                "1",
                "-vf",
                "scale=1280:-1",
                str(fallback),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        frame_files = [fallback] if fallback.exists() else []
        timestamps = [1.0]
    frames = [
        {
            "path": to_project_relative(path, root_path),
            "video_id": video_id,
            "timestamp": timestamps[index] if index < len(timestamps) else None,
            "source_video_path": to_project_relative(media, root_path),
            "source_type": "scene_frame",
        }
        for index, path in enumerate(frame_files)
    ]
    atomic_write_json(manifest_path, frames, root_path)
    return frames


def extract_frames_batch(
    root: str | Path | None = None,
    limit: int | None = None,
    content_type: str | None = None,
    offset: int = 0,
    scene_threshold: float | None = None,
    max_frames: int | None = None,
    force: bool = False,
) -> dict[str, int]:
    root_path = Path(root or ".").resolve()
    configure_local_environment(root_path)
    config = load_project_config(root_path)
    threshold = scene_threshold if scene_threshold is not None else float(config["media"]["frame_scene_threshold"])
    max_count = max_frames if max_frames is not None else int(config["media"]["frame_max_per_video"])
    entries = select_catalog_entries(root_path, limit=limit, content_type=content_type, offset=offset)
    result: dict[str, int] = {}
    for index, entry in enumerate(entries, start=1):
        video_id = entry["video_id"]
        media = first_media_file(root_path, video_id, "video-light")
        if not media:
            continue
        print(f"[frames] {index}/{len(entries)} {entry.get('published_at') or 'unknown'} {video_id} {entry.get('title', '')}")
        frames = extract_candidate_frames(
            root_path,
            video_id,
            media,
            scene_threshold=threshold,
            max_frames=max_count,
            force=force,
        )
        result[video_id] = len(frames)
    return result


def _json_safe(value: Any) -> Any:
    """Convert Paddle/numpy-heavy objects into normal JSON values."""

    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return value.as_posix()
    if hasattr(value, "tolist"):
        return _json_safe(value.tolist())
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:  # pragma: no cover - defensive for third-party scalar wrappers
            pass
    return value


def _paddle_result_to_dict(result: Any) -> dict[str, Any]:
    if hasattr(result, "json"):
        return _json_safe(result.json)
    if hasattr(result, "to_dict"):
        return _json_safe(result.to_dict())
    return {"raw": _json_safe(result)}


def _recognized_items(result_dicts: list[dict[str, Any]], min_score: float) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for result in result_dicts:
        res = result.get("res", result)
        texts = res.get("rec_texts") or []
        scores = res.get("rec_scores") or []
        boxes = res.get("rec_boxes") or res.get("rec_polys") or []
        for index, text in enumerate(texts):
            clean_text = str(text).strip()
            if not clean_text:
                continue
            score = float(scores[index]) if index < len(scores) else None
            if score is not None and score < min_score:
                continue
            items.append(
                {
                    "text": clean_text,
                    "score": score,
                    "box": _json_safe(boxes[index]) if index < len(boxes) else None,
                }
            )
    return items


def run_paddle_ocr(
    root: str | Path | None,
    video_id: str,
    *,
    force: bool = False,
    min_score: float = 0.5,
) -> list[dict[str, object]]:
    """Run PaddleOCR on extracted frames if the optional dependency exists."""

    root_path = Path(root or ".").resolve()
    configure_local_environment(root_path)
    config = load_project_config(root_path)
    try:
        from paddleocr import PaddleOCR  # type: ignore
    except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("Missing PaddleOCR. Install optional ml extras first.") from exc

    frame_dir = root_path / config["storage"]["analysis_dir"] / "frames" / video_id
    output_dir = root_path / config["storage"]["analysis_dir"] / "ocr" / video_id
    output_path = output_dir / "ocr.json"
    if output_path.exists() and not force:
        return json.loads(output_path.read_text(encoding="utf-8"))

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = frame_dir / "frames.json"
    frame_meta = {}
    if manifest_path.exists():
        frame_meta = {row.get("path"): row for row in json.loads(manifest_path.read_text(encoding="utf-8"))}

    # PaddleOCR 3.x Python API. Disable document pre-processors for chart frames:
    # they are screenshots, not scanned pages, and this avoids extra model noise.
    ocr = PaddleOCR(
        lang="vi",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        text_rec_score_thresh=0.35,
    )
    rows: list[dict[str, object]] = []
    for frame in sorted(frame_dir.glob("*.jpg")):
        relative_frame = to_project_relative(frame, root_path)
        result = ocr.predict(str(frame))
        result_dicts = [_paddle_result_to_dict(item) for item in result]
        items = _recognized_items(result_dicts, min_score=min_score)
        rows.append(
            {
                "video_id": video_id,
                "frame_path": relative_frame,
                "timestamp": frame_meta.get(relative_frame, {}).get("timestamp"),
                "source_type": "ocr_paddleocr",
                "text": " ".join(item["text"] for item in items),
                "items": items,
                "result": result_dicts,
            }
        )
    output_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return rows


def ocr_frames_batch(
    root: str | Path | None = None,
    limit: int | None = None,
    content_type: str | None = None,
    offset: int = 0,
    force: bool = False,
) -> dict[str, int]:
    root_path = Path(root or ".").resolve()
    configure_local_environment(root_path)
    config = load_project_config(root_path)
    entries = select_catalog_entries(root_path, limit=limit, content_type=content_type, offset=offset)
    result: dict[str, int] = {}
    for index, entry in enumerate(entries, start=1):
        video_id = entry["video_id"]
        frame_dir = root_path / config["storage"]["analysis_dir"] / "frames" / video_id
        if not frame_dir.exists():
            continue
        print(f"[ocr] {index}/{len(entries)} {entry.get('published_at') or 'unknown'} {video_id} {entry.get('title', '')}")
        rows = run_paddle_ocr(root_path, video_id, force=force)
        result[video_id] = len(rows)
    return result
