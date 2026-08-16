"""Reprocess videos for a calendar year — reuse media, force ASR/clean/extract.

Chạy:
  rtk uv run python scripts/run_reprocess_year.py --root H:\\cai-nghien-trading-local-rag --year 2026 --status
  rtk uv run python scripts/run_reprocess_year.py --root H:\\cai-nghien-trading-local-rag --year 2026
  rtk uv run python scripts/run_reprocess_year.py --year 2026 --stop-after layer-b
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

from cai_nghien_assistant.asr import asr_batch
from cai_nghien_assistant.config import load_project_config
from cai_nghien_assistant.frames import extract_frames_batch, ocr_frames_batch
from cai_nghien_assistant.knowledge_extraction.batch import run_extract_batch
from cai_nghien_assistant.media import fetch_audio_batch, fetch_video_light_batch
from cai_nghien_assistant.paths import configure_local_environment
from cai_nghien_assistant.transcript_quality.batch import run_clean_batch
from cai_nghien_assistant.transcript_quality.review_store import reset_videos_for_reprocess
from cai_nghien_assistant.transcripts import normalize_all_transcripts
from cai_nghien_assistant.youtube_collect import catalog_entries_filtered

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from run_full_pipeline import STAGES, artifact_ok, manifest_ok


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def local_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def state_path(root: Path, year: int) -> Path:
    return root / "data" / "analysis" / "state" / f"reprocess_{year}.json"


def log_path(root: Path, year: int) -> Path:
    return root / "logs" / "reprocess" / f"{local_stamp()}-{year}.log"


class Logger:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = path.open("a", encoding="utf-8", errors="replace")

    def line(self, text: str = "") -> None:
        msg = f"[{dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {text}"
        self.handle.write(msg + "\n")
        self.handle.flush()
        print(msg, flush=True)

    def close(self) -> None:
        self.handle.close()


def summarize(root: Path, entries: list[dict[str, Any]]) -> dict[str, int]:
    summary = {"total": len(entries)}
    for stage in STAGES:
        summary[stage] = sum(1 for entry in entries if artifact_ok(root, entry["video_id"], stage))
    return summary


def reprocess_config(root: Path) -> dict[str, Any]:
    return dict(load_project_config(root).get("pipeline", {}).get("reprocess") or {})


def process_video_layer_a(
    root: Path,
    entry: dict[str, Any],
    *,
    content_type: str,
    cfg: dict[str, Any],
    logger: Logger,
) -> None:
    video_id = entry["video_id"]
    logger.line(f"layer-a video_id={video_id} date={entry.get('published_at')} title={entry.get('title', '')}")

    if not manifest_ok(root, video_id, "audio"):
        logger.line("  fetch-audio (missing or invalid manifest)")
        fetch_audio_batch(root, video_id=video_id, force=True)
    else:
        logger.line("  fetch-audio skip (manifest ok)")

    if not manifest_ok(root, video_id, "video-light"):
        logger.line("  fetch-video-light (missing or invalid manifest)")
        fetch_video_light_batch(root, video_id=video_id, force=True)
    else:
        logger.line("  fetch-video-light skip (manifest ok)")

    logger.line("  asr --force")
    asr_batch(
        root,
        video_id=video_id,
        model_size=str(cfg.get("model_size") or "large-v3"),
        device=str(cfg.get("device") or "cuda"),
        compute_type=str(cfg.get("compute_type") or "float16"),
        beam_size=int(cfg.get("beam_size") or 8),
        force=True,
    )

    logger.line("  extract-frames --force")
    try:
        extract_frames_batch(root, video_id=video_id, force=True)
    except Exception as exc:
        logger.line(f"  extract-frames FAILED: {exc}")

    logger.line("  ocr-frames --force")
    try:
        ocr_frames_batch(root, video_id=video_id, force=True)
    except Exception as exc:
        logger.line(f"  ocr-frames FAILED (continuing): {exc}")


def run_layer_b(root: Path, year: int, content_type: str, cfg: dict[str, Any], logger: Logger) -> None:
    logger.line("layer-b normalize-transcripts")
    normalize_all_transcripts(root, content_type=content_type, published_year=year)

    logger.line("layer-b clean conservative-refine --force")
    run_clean_batch(
        root,
        content_type=content_type,
        published_year=year,
        model_id="conservative-refine",
        engine="conservative-refine",
        force=True,
    )

    if bool(cfg.get("enable_asr_reprocess", True)):
        logger.line("layer-b clean asr-reprocess")
        run_clean_batch(
            root,
            content_type=content_type,
            published_year=year,
            model_id="asr-reprocess",
            engine="asr-reprocess",
            force=False,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reprocess corpus for one published year.")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--content-type", default=None, help="Default: config pipeline.reprocess.content_type")
    parser.add_argument("--status", action="store_true", help="Print summary only.")
    parser.add_argument("--no-reset", action="store_true", help="Skip reset review/AI before reprocess.")
    parser.add_argument("--skip-layer-a", action="store_true", help="Skip media/ASR/OCR (layer-a already done).")
    parser.add_argument(
        "--stop-after",
        choices=("layer-a", "layer-b", "layer-d"),
        default=None,
        help="Stop after a layer (default: full through layer-d).",
    )
    args = parser.parse_args(argv)

    root = args.root.resolve()
    configure_local_environment(root)
    cfg = reprocess_config(root)
    content_type = args.content_type or str(cfg.get("content_type") or "regular+livestream")
    year = args.year

    entries = catalog_entries_filtered(root, content_type=content_type, published_year=year)
    print(json.dumps({"year": year, "content_type": content_type, "videos": len(entries)}, ensure_ascii=False, indent=2))
    if args.status:
        print(json.dumps(summarize(root, entries), ensure_ascii=False, indent=2))
        return 0

    if not entries:
        print("No catalog entries for this year/filter.", file=sys.stderr)
        return 1

    logger = Logger(log_path(root, year))
    try:
        video_ids = [entry["video_id"] for entry in entries]
        if not args.no_reset and bool(cfg.get("reset_review", True)):
            logger.line(f"reset review for {len(video_ids)} videos")
            reset_videos_for_reprocess(root, video_ids)

        if not args.skip_layer_a:
            logger.line(f"layer-a begin count={len(entries)}")
            for entry in entries:
                process_video_layer_a(root, entry, content_type=content_type, cfg=cfg, logger=logger)

            if args.stop_after == "layer-a":
                logger.line("stopped after layer-a")
                return 0
        else:
            logger.line("layer-a skipped")

        run_layer_b(root, year, content_type, cfg, logger)
        if args.stop_after == "layer-b":
            logger.line("stopped after layer-b")
            return 0

        logger.line("layer-d extract-knowledge --force")
        result = run_extract_batch(root, content_type=content_type, published_year=year, force=True)
        logger.line(f"extract-knowledge done: {json.dumps(result, ensure_ascii=False)}")
        return 0
    finally:
        logger.close()


if __name__ == "__main__":
    raise SystemExit(main())
