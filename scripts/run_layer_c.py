"""Lớp C: build-index — approved nếu đã duyệt, không thì ai_cleaned (provisional).

Chạy ngắn:
  rtk uv run python scripts/run_layer_c.py --root H:\\cai-nghien-trading-local-rag

Tùy chọn mở UI review:
  rtk uv run python scripts/run_layer_c.py --root H:\\cai-nghien-trading-local-rag --review-ui
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from _runner_common import resolve_root, run_cnga


def count_transcript_sources(root: Path) -> dict[str, int]:
    tq = root / "data" / "analysis" / "transcript_quality"
    approved = 0
    ai_only = 0
    for path in tq.iterdir() if tq.exists() else []:
        if not path.is_dir():
            continue
        state_path = path / "review_state.json"
        if state_path.exists():
            state = json.loads(state_path.read_text(encoding="utf-8"))
            if state.get("status") == "approved" and (path / "approved.jsonl").exists():
                approved += 1
                continue
        if (path / "ai_cleaned.jsonl").exists():
            ai_only += 1
    return {"approved_videos": approved, "ai_provisional_videos": ai_only}


def main() -> int:
    parser = argparse.ArgumentParser(description="Lớp C — index truy hồi (approved ưu tiên).")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--review-ui", action="store_true", help="Mở review UI sau khi build-index.")
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()

    root = resolve_root(args.root)
    counts = count_transcript_sources(root)
    print(
        "Transcript cho index: "
        f"{counts['approved_videos']} approved, "
        f"{counts['ai_provisional_videos']} AI provisional (chưa approve).",
        flush=True,
    )

    run_cnga(root, "build-index")

    if args.review_ui:
        port_args: list[str] = []
        if args.port:
            port_args = ["--port", str(args.port)]
        subprocess.run(
            [sys.executable, "-m", "cai_nghien_assistant.cli", "--root", str(root), "review-ui", *port_args],
            cwd=str(root),
            check=False,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
