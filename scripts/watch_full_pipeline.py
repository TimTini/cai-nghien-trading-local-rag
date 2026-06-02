"""Watchdog for the unattended full pipeline.

Writes a compact heartbeat every minute and resumes the runner if it is not
alive while the corpus is still incomplete. This is intentionally separate from
the heavy runner so it can be started/stopped without interrupting ASR/OCR.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from run_full_pipeline import STAGES, artifact_ok, catalog_entries, read_json, summarize, utc_now, write_json


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def log_line(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = f"[{dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {text}"
    with path.open("a", encoding="utf-8", errors="replace") as handle:
        handle.write(line + "\n")
    print(line, flush=True)


def process_alive(pid: int | None) -> bool:
    if not pid:
        return False
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            f"if (Get-Process -Id {int(pid)} -ErrorAction SilentlyContinue) {{ 'alive' }}",
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    return "alive" in completed.stdout


def running_stages(state: dict[str, Any]) -> list[tuple[int | None, str, str]]:
    running: list[tuple[int | None, str, str]] = []
    for video_id, item in (state.get("videos") or {}).items():
        for stage, stage_data in (item.get("stages") or {}).items():
            if stage_data.get("status") == "running":
                running.append((item.get("offset"), video_id, stage))
    return sorted(running, key=lambda row: (row[0] if row[0] is not None else 999999, row[1], row[2]))


def failed_stages(state: dict[str, Any]) -> list[tuple[int | None, str, str, str]]:
    failed: list[tuple[int | None, str, str, str]] = []
    for video_id, item in (state.get("videos") or {}).items():
        for stage, stage_data in (item.get("stages") or {}).items():
            if stage_data.get("status") == "failed":
                failed.append((item.get("offset"), video_id, stage, str(stage_data.get("error") or "")))
    return sorted(failed, key=lambda row: (row[0] if row[0] is not None else 999999, row[1], row[2]))


def failed_artifacts_recovered(root: Path, failures: list[tuple[int | None, str, str, str]]) -> bool:
    if not failures:
        return False
    return all(artifact_ok(root, video_id, stage) for _, video_id, stage, _ in failures)


def is_complete(summary: dict[str, int]) -> bool:
    total = int(summary.get("total") or 0)
    return total > 0 and all(int(summary.get(stage) or 0) >= total for stage in STAGES)


def start_runner(root: Path, content_type: str, state_dir: Path, log_dir: Path, log_path: Path) -> None:
    run_stamp = stamp()
    out_path = log_dir / f"background-resume-{run_stamp}.out.log"
    err_path = log_dir / f"background-resume-{run_stamp}.err.log"
    command = ["rtk", "uv", "run", "python", "scripts/run_full_pipeline.py", "--root", str(root), "--content-type", content_type]
    out = out_path.open("a", encoding="utf-8", errors="replace")
    err = err_path.open("a", encoding="utf-8", errors="replace")
    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    process = subprocess.Popen(command, cwd=str(root), stdout=out, stderr=err, creationflags=creationflags)
    pid_path = state_dir / f"full_pipeline_{content_type}.pid.json"
    write_json(
        pid_path,
        {
            "pid": process.pid,
            "started_at": dt.datetime.now().isoformat(),
            "out": str(out_path),
            "err": str(err_path),
            "command": " ".join(command),
            "started_by": "watch_full_pipeline.py",
        },
    )
    log_line(log_path, f"resumed runner pid={process.pid} out={out_path.name}")


def run(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    state_dir = root / "data" / "analysis" / "state"
    log_dir = root / "logs" / "full-pipeline"
    log_path = log_dir / f"watchdog-{stamp()}-{args.content_type}.log"
    state_path = state_dir / f"full_pipeline_{args.content_type}.json"
    pid_path = state_dir / f"full_pipeline_{args.content_type}.pid.json"
    log_line(log_path, f"watchdog start root={root} interval={args.interval_seconds}s")

    while True:
        entries = catalog_entries(root, args.content_type)
        summary = summarize(root, entries)
        state = read_json(state_path, {})
        pid_info = read_json(pid_path, {})
        pid = int(pid_info.get("pid") or state.get("runner_pid") or 0) or None
        alive = process_alive(pid)
        running = running_stages(state)
        failures = failed_stages(state)
        latest_log = state.get("latest_log") or ""
        latest_log_path = root / latest_log if latest_log else None
        latest_size = latest_log_path.stat().st_size if latest_log_path and latest_log_path.exists() else -1
        message = (
            f"alive={alive} pid={pid} summary={json.dumps(summary, sort_keys=True)} "
            f"running={running[-3:]} failures={failures[-3:]} latest_log={latest_log} size={latest_size}"
        )
        log_line(log_path, message)

        recovered_failures = failed_artifacts_recovered(root, failures)
        if failures and not recovered_failures:
            log_line(log_path, "failure detected; retrying after runner exit")
        elif recovered_failures:
            log_line(log_path, "failure artifacts recovered; resume allowed after runner exit")

        if is_complete(summary):
            log_line(log_path, "complete")
            return 0

        if not alive:
            start_runner(root, args.content_type, state_dir, log_dir, log_path)

        if args.once:
            return 0
        time.sleep(args.interval_seconds)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Heartbeat/resume watchdog for full cnga pipeline.")
    parser.add_argument("--root", default=".", type=Path)
    parser.add_argument("--content-type", default="regular", choices=["regular", "livestream", "short"])
    parser.add_argument("--interval-seconds", type=int, default=60)
    parser.add_argument("--once", action="store_true")
    return parser


if __name__ == "__main__":
    raise SystemExit(run(build_parser().parse_args()))
