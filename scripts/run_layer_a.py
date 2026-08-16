"""Lớp A: thu thập media + ASR + frame/OCR + index (regular + livestream).

Chạy ngắn:
  rtk uv run python scripts/run_layer_a.py --root H:\\cai-nghien-trading-local-rag

Hoặc trực tiếp (cùng mặc định sau khi load config):
  rtk uv run python scripts/run_full_pipeline.py --root H:\\cai-nghien-trading-local-rag
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from _runner_common import load_toml_section, resolve_root


def main() -> int:
    parser = argparse.ArgumentParser(description="Lớp A — full media/ASR/OCR pipeline (regular+livestream).")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--status", action="store_true", help="Chỉ xem tiến độ, không chạy.")
    parser.add_argument("--stop-on-error", action="store_true")
    args, extra = parser.parse_known_args()

    root = resolve_root(args.root)
    cfg = load_toml_section(root, "pipeline", "full_run")
    command = [
        sys.executable,
        str(root / "scripts" / "run_full_pipeline.py"),
        "--root",
        str(root),
        "--content-type",
        str(cfg.get("content_type") or "regular+livestream"),
        "--model-size",
        str(cfg.get("model_size") or "large-v3"),
        "--device",
        str(cfg.get("device") or "cuda"),
        "--compute-type",
        str(cfg.get("compute_type") or "float16"),
        "--beam-size",
        str(int(cfg.get("beam_size") or 8)),
        "--index-every",
        str(int(cfg.get("index_every") or 10)),
    ]
    if args.status:
        command.append("--status")
    if args.stop_on_error:
        command.append("--stop-on-error")
    command.extend(extra)
    print("$ " + " ".join(command), flush=True)
    return int(subprocess.run(command, cwd=str(root), check=False).returncode)


if __name__ == "__main__":
    raise SystemExit(main())
