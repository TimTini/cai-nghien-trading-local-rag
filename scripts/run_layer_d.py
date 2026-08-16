"""Lớp D: trích xuất kiến thức có cấu trúc từ transcript + OCR.

Chạy ngắn:
  rtk uv run python scripts/run_layer_d.py --root H:\\cai-nghien-trading-local-rag
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _runner_common import content_type_arg, load_toml_section, resolve_root, run_cnga


def main() -> int:
    parser = argparse.ArgumentParser(description="Lớp D — extract knowledge facts (deterministic).")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--force", action="store_true", help="Ghi đè facts.jsonl đã có.")
    args, extra = parser.parse_known_args()

    root = resolve_root(args.root)
    cfg = load_toml_section(root, "pipeline", "layer_d")
    ctype = content_type_arg(str(cfg.get("content_type") or ""))

    command = ["extract-knowledge", *ctype]
    if args.force:
        command.append("--force")
    command.extend(extra)
    run_cnga(root, *command)
    print("Lớp D xong. Output: data/analysis/knowledge/", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
