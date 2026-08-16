"""Lớp B: normalize transcript + clean (conservative-refine, tùy chọn asr-reprocess).

Chạy ngắn:
  rtk uv run python scripts/run_layer_b.py --root H:\\cai-nghien-trading-local-rag
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _runner_common import content_type_arg, load_toml_section, resolve_root, run_cnga


def main() -> int:
    parser = argparse.ArgumentParser(description="Lớp B — transcript 3 tầng (raw → ai_cleaned).")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--skip-normalize", action="store_true")
    parser.add_argument("--skip-clean", action="store_true")
    parser.add_argument("--force-clean", action="store_true", help="Re-clean khi đổi logic/model.")
    parser.add_argument("--asr-reprocess", action="store_true", help="Chạy thêm engine asr-reprocess (GPU).")
    parser.add_argument("--asr-reprocess-limit", type=int, default=None)
    args = parser.parse_args()

    root = resolve_root(args.root)
    cfg = load_toml_section(root, "pipeline", "layer_b")
    ctype = content_type_arg(str(cfg.get("content_type") or ""))

    if not args.skip_normalize:
        run_cnga(root, "normalize-transcripts", *ctype)

    if not args.skip_clean:
        clean_args = [
            "clean-transcripts",
            "--engine",
            "conservative-refine",
            "--model-id",
            "conservative-refine",
            *ctype,
        ]
        if args.force_clean:
            clean_args.append("--force")
        run_cnga(root, *clean_args)

        do_reprocess = args.asr_reprocess or not bool(cfg.get("skip_asr_reprocess"))
        limit = args.asr_reprocess_limit
        if limit is None and cfg.get("asr_reprocess_limit"):
            limit = int(cfg["asr_reprocess_limit"])
        if do_reprocess and (limit is None or limit > 0):
            re_args = [
                "clean-transcripts",
                "--engine",
                "asr-reprocess",
                "--model-id",
                "asr-reprocess",
                *ctype,
            ]
            if limit and limit > 0:
                re_args.extend(["--limit", str(limit)])
            run_cnga(root, *re_args)

    print("Lớp B xong. Mở review: uv run cnga review-ui", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
