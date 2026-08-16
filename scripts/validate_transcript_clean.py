"""So sánh metric trước/sau clean — chạy local, không cloud."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from cai_nghien_assistant.paths import configure_local_environment
from cai_nghien_assistant.transcript_quality.cleaner import clean_all_segments
from cai_nghien_assistant.transcript_quality.metrics import (
    garbage_char_count,
    readable_sentence_ratio,
    segment_quality_score,
)
from cai_nghien_assistant.transcript_quality.raw_layer import ensure_raw_layer, ordered_video_ids_with_transcripts


def aggregate_metrics(segments: list) -> dict[str, float]:
    if not segments:
        return {"segments": 0, "garbage_chars": 0, "readable_sentence_ratio": 0.0}
    garbage = 0
    readable_sum = 0.0
    for seg in segments:
        garbage += garbage_char_count(seg.text)
        readable_sum += readable_sentence_ratio(seg.text)
    n = len(segments)
    return {
        "segments": n,
        "garbage_chars": garbage,
        "readable_sentence_ratio": round(readable_sum / n, 4),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate transcript cleaning metrics")
    parser.add_argument("--root", default=".", help="Project root")
    parser.add_argument("--video-ids", nargs="*", default=None, help="Explicit video IDs")
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--engine", default="conservative-refine")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    configure_local_environment(root)

    video_ids = args.video_ids
    if not video_ids:
        video_ids = ordered_video_ids_with_transcripts(root)[: args.limit]
    if not video_ids:
        print("No transcripts found under data/analysis/transcripts/", file=sys.stderr)
        return 1

    report: list[dict] = []
    for video_id in video_ids:
        segments, _, _ = ensure_raw_layer(root, video_id)
        if not segments:
            continue
        before = aggregate_metrics(segments)
        cleaned, changes = clean_all_segments(
            segments,
            root=root,
            engine=args.engine,
        )
        after = aggregate_metrics(cleaned)
        report.append(
            {
                "video_id": video_id,
                "engine": args.engine,
                "before": before,
                "after": after,
                "changes": len(changes),
                "sample_segments": [
                    {
                        "segment_id": seg.segment_id,
                        "before_score": segment_quality_score(
                            next(s.text for s in segments if s.segment_id == seg.segment_id)
                        ),
                        "after_score": segment_quality_score(seg.text),
                    }
                    for seg in cleaned[:2]
                ],
            }
        )

    print(json.dumps({"videos": report}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
