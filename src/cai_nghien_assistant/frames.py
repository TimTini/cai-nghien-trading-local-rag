"""Candidate frame extraction and OCR helpers.

This module keeps vision work sparse: detect candidate frames by code first,
then run OCR/local vision only on selected timestamps.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .config import load_project_config
from .paths import configure_local_environment, to_project_relative
from .storage import atomic_write_json


def extract_candidate_frames(
    root: str | Path | None,
    video_id: str,
    media_path: str | Path,
    scene_threshold: float = 0.35,
) -> list[dict[str, str]]:
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
    output_dir.mkdir(parents=True, exist_ok=True)
    pattern = output_dir / "scene-%05d.jpg"
    command = [
        "ffmpeg",
        "-hide_banner",
        "-i",
        str(media),
        "-vf",
        f"select='gt(scene,{scene_threshold})',metadata=print",
        "-vsync",
        "vfr",
        str(pattern),
    ]
    subprocess.run(command, check=True)
    frames = [{"path": to_project_relative(path, root_path), "video_id": video_id} for path in sorted(output_dir.glob("*.jpg"))]
    atomic_write_json(output_dir / "frames.json", frames, root_path)
    return frames


def run_paddle_ocr(root: str | Path | None, video_id: str) -> list[dict[str, object]]:
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
    output_dir.mkdir(parents=True, exist_ok=True)

    ocr = PaddleOCR(lang="vi", use_angle_cls=True)
    rows: list[dict[str, object]] = []
    for frame in sorted(frame_dir.glob("*.jpg")):
        result = ocr.ocr(str(frame), cls=True)
        rows.append(
            {
                "video_id": video_id,
                "frame_path": to_project_relative(frame, root_path),
                "source_type": "ocr_paddleocr",
                "result": result,
            }
        )
    (output_dir / "ocr.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return rows

