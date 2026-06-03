"""Run the YouTube evidence pipeline unattended with log/resume.

This script intentionally calls the public ``cnga`` CLI one video at a time.
That is slower than one huge command, but it gives clean resume semantics:
completed artifacts are detected before each stage, failures are recorded per
video, and the next run can continue without redoing successful work.
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

from cai_nghien_assistant.paths import configure_local_environment
from cai_nghien_assistant.youtube_collect import load_latest_catalog


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

STAGES = ("fetch-audio", "fetch-video-light", "asr", "extract-frames", "ocr-frames")
NATIVE_CRASH_RETURN_CODES = {
    1073807364,  # Windows native control/terminate event, seen from PaddleOCR.
    3221225786,  # STATUS_CONTROL_C_EXIT.
    3221226091,  # Native fail-fast style crash, seen after OCR process failure.
}
UNAVAILABLE_VIDEO_MARKERS = (
    "This video is not available",
    "Video unavailable",
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def local_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


class Logger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a", encoding="utf-8", errors="replace")

    def line(self, text: str = "") -> None:
        message = f"[{dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {text}"
        self.handle.write(message + "\n")
        self.handle.flush()
        try:
            print(message, flush=True)
        except Exception:
            pass

    def raw(self, text: str) -> None:
        self.handle.write(text)
        self.handle.flush()
        try:
            print(text, end="", flush=True)
        except Exception:
            pass

    def close(self) -> None:
        self.handle.close()


def project_rel(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def catalog_entries(root: Path, content_type: str) -> list[dict[str, Any]]:
    entries = load_latest_catalog(root)
    if content_type:
        entries = [entry for entry in entries if entry.get("content_type") == content_type]
    return entries


def manifest_ok(root: Path, video_id: str, media_kind: str) -> bool:
    manifest_path = root / "data" / "raw" / "videos" / video_id / media_kind / "manifest.json"
    if not manifest_path.exists():
        return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    files = manifest.get("files") or []
    if not files:
        return False
    for item in files:
        rel_path = item.get("path")
        if not rel_path:
            return False
        media_file = root / str(rel_path)
        if not media_file.exists() or media_file.stat().st_size <= 0:
            return False
    return True


def asr_ok(root: Path, video_id: str) -> bool:
    transcript_path = root / "data" / "analysis" / "transcripts" / video_id / "asr_faster_whisper.jsonl"
    meta_path = root / "data" / "analysis" / "transcripts" / video_id / "asr_faster_whisper.meta.json"
    return transcript_path.exists() and meta_path.exists()


def frames_ok(root: Path, video_id: str) -> bool:
    frames_path = root / "data" / "analysis" / "frames" / video_id / "frames.json"
    if not frames_path.exists():
        return False
    try:
        rows = json.loads(frames_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return isinstance(rows, list) and bool(rows)


def ocr_ok(root: Path, video_id: str) -> bool:
    frames_path = root / "data" / "analysis" / "frames" / video_id / "frames.json"
    ocr_path = root / "data" / "analysis" / "ocr" / video_id / "ocr.json"
    if not frames_path.exists() or not ocr_path.exists():
        return False
    try:
        frames = json.loads(frames_path.read_text(encoding="utf-8"))
        ocr = json.loads(ocr_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return isinstance(ocr, list) and len(ocr) >= len(frames)


def artifact_ok(root: Path, video_id: str, stage: str) -> bool:
    if stage == "fetch-audio":
        return manifest_ok(root, video_id, "audio")
    if stage == "fetch-video-light":
        return manifest_ok(root, video_id, "video-light")
    if stage == "asr":
        return asr_ok(root, video_id)
    if stage == "extract-frames":
        return frames_ok(root, video_id)
    if stage == "ocr-frames":
        return ocr_ok(root, video_id)
    raise ValueError(f"Unknown stage: {stage}")


def stage_dependencies_ok(root: Path, video_id: str, stage: str) -> bool:
    if stage == "asr":
        return manifest_ok(root, video_id, "audio")
    if stage == "extract-frames":
        return manifest_ok(root, video_id, "video-light")
    if stage == "ocr-frames":
        return frames_ok(root, video_id)
    return True


def stage_command(args: argparse.Namespace, stage: str, offset: int) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "cai_nghien_assistant.cli",
        "--root",
        str(args.root),
        stage,
        "--limit",
        "1",
        "--offset",
        str(offset),
        "--content-type",
        args.content_type,
    ]
    if stage == "asr":
        command.extend(
            [
                "--model-size",
                args.model_size,
                "--device",
                args.device,
                "--compute-type",
                args.compute_type,
                "--beam-size",
                str(args.beam_size),
            ]
        )
        if args.vad_filter:
            command.append("--vad-filter")
    return command


def run_command(command: list[str], root: Path, logger: Logger) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["CNGA_PROJECT_ROOT"] = str(root)
    started = time.monotonic()
    logger.line("$ " + " ".join(command))
    process = subprocess.Popen(
        command,
        cwd=str(root),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert process.stdout is not None
    output_parts: list[str] = []
    for line in process.stdout:
        output_parts.append(line)
        logger.raw(line)
    return_code = process.wait()
    elapsed = time.monotonic() - started
    logger.line(f"exit={return_code} elapsed={elapsed:.1f}s")
    return return_code, "".join(output_parts)


def output_says_video_unavailable(output: str) -> bool:
    return any(marker in output for marker in UNAVAILABLE_VIDEO_MARKERS)


def video_state(state: dict[str, Any], entry: dict[str, Any], offset: int) -> dict[str, Any]:
    videos = state.setdefault("videos", {})
    video_id = entry["video_id"]
    current = videos.setdefault(video_id, {})
    current.update(
        {
            "offset": offset,
            "published_at": entry.get("published_at") or "",
            "title": entry.get("title") or "",
            "updated_at": utc_now(),
        }
    )
    current.setdefault("stages", {})
    return current


def mark_stage(video: dict[str, Any], stage: str, status: str, **extra: Any) -> None:
    stage_data = video.setdefault("stages", {}).setdefault(stage, {})
    stage_data.update({"status": status, "updated_at": utc_now(), **extra})
    if status != "failed" and "error" not in extra:
        stage_data.pop("error", None)


def summarize(root: Path, entries: list[dict[str, Any]]) -> dict[str, int]:
    summary = {"total": len(entries)}
    for stage in STAGES:
        summary[stage] = sum(1 for entry in entries if artifact_ok(root, entry["video_id"], stage))
    return summary


def print_status(root: Path, entries: list[dict[str, Any]], state_path: Path) -> None:
    summary = summarize(root, entries)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if state_path.exists():
        state = read_json(state_path, {})
        failures = []
        for video_id, item in (state.get("videos") or {}).items():
            for stage, stage_data in (item.get("stages") or {}).items():
                if stage_data.get("status") == "failed" and not artifact_ok(root, video_id, stage):
                    failures.append({"video_id": video_id, "stage": stage, "error": stage_data.get("error", "")})
        if failures:
            print("failures:")
            print(json.dumps(failures[-20:], ensure_ascii=False, indent=2))


def build_index(args: argparse.Namespace, root: Path, logger: Logger, state: dict[str, Any], state_path: Path) -> int:
    logger.line("build-index")
    code, _output = run_command(
        [sys.executable, "-m", "cai_nghien_assistant.cli", "--root", str(root), "build-index"], root, logger
    )
    state.setdefault("index_runs", []).append({"status": "done" if code == 0 else "failed", "return_code": code, "at": utc_now()})
    state["updated_at"] = utc_now()
    write_json(state_path, state)
    return code


def run(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    configure_local_environment(root)
    state_path = root / "data" / "analysis" / "state" / f"full_pipeline_{args.content_type}.json"
    entries = catalog_entries(root, args.content_type)
    if args.status:
        print_status(root, entries, state_path)
        return 0

    log_path = root / "logs" / "full-pipeline" / f"{local_stamp()}-{args.content_type}.log"
    state = read_json(
        state_path,
        {
            "schema": 1,
            "content_type": args.content_type,
            "created_at": utc_now(),
            "videos": {},
            "index_runs": [],
        },
    )
    state.update(
        {
            "root": str(root),
            "content_type": args.content_type,
            "model_size": args.model_size,
            "device": args.device,
            "compute_type": args.compute_type,
            "beam_size": args.beam_size,
            "status": "running",
            "runner_pid": os.getpid(),
            "run_started_at": utc_now(),
            "updated_at": utc_now(),
            "latest_log": project_rel(root, log_path),
        }
    )
    write_json(state_path, state)

    if args.end_offset is not None:
        entries_to_run = list(enumerate(entries))[args.start_offset : args.end_offset]
    else:
        entries_to_run = list(enumerate(entries))[args.start_offset :]

    logger = Logger(log_path)
    failures = 0
    run_failures: list[dict[str, Any]] = []
    processed_since_index = 0
    try:
        logger.line(f"root={root}")
        logger.line(f"state={state_path}")
        logger.line(f"content_type={args.content_type} total={len(entries)} selected={len(entries_to_run)}")
        logger.line(f"initial_summary={json.dumps(summarize(root, entries), ensure_ascii=False, sort_keys=True)}")
        run_command([sys.executable, "-m", "cai_nghien_assistant.cli", "--root", str(root), "doctor"], root, logger)

        for offset, entry in entries_to_run:
            video_id = entry["video_id"]
            video = video_state(state, entry, offset)
            logger.line(f"video offset={offset} id={video_id} date={entry.get('published_at')} title={entry.get('title', '')}")
            video_failed = False
            for stage in STAGES:
                if artifact_ok(root, video_id, stage):
                    mark_stage(video, stage, "done", reason="artifact-present")
                    write_json(state_path, state)
                    continue
                if not stage_dependencies_ok(root, video_id, stage):
                    mark_stage(video, stage, "skipped", reason="missing-dependency")
                    write_json(state_path, state)
                    continue

                mark_stage(video, stage, "running", started_at=utc_now())
                state["updated_at"] = utc_now()
                write_json(state_path, state)
                code, output = run_command(stage_command(args, stage, offset), root, logger)
                if code == 0 and not artifact_ok(root, video_id, stage):
                    if stage in {"fetch-audio", "fetch-video-light"} and output_says_video_unavailable(output):
                        mark_stage(video, stage, "skipped", reason="video-unavailable", return_code=code)
                        logger.line(f"{stage} unavailable; skipping video_id={video_id}")
                        state["updated_at"] = utc_now()
                        write_json(state_path, state)
                        continue
                    logger.line(f"{stage} returned 0 but artifact is missing; retrying once with --force")
                    code, output = run_command(stage_command(args, stage, offset) + ["--force"], root, logger)
                if code == 0 and artifact_ok(root, video_id, stage):
                    mark_stage(video, stage, "done", return_code=code)
                    processed_since_index += 1
                else:
                    if stage in {"fetch-audio", "fetch-video-light"} and output_says_video_unavailable(output):
                        mark_stage(video, stage, "skipped", reason="video-unavailable", return_code=code)
                        logger.line(f"{stage} unavailable; skipping video_id={video_id}")
                        state["updated_at"] = utc_now()
                        state["failures"] = run_failures
                        write_json(state_path, state)
                        continue
                    failures += 1
                    video_failed = True
                    mark_stage(video, stage, "failed", return_code=code, error=f"{stage} return_code={code}")
                    run_failures.append({"video_id": video_id, "stage": stage, "error": f"{stage} return_code={code}"})
                    logger.line(f"failed video_id={video_id} stage={stage}")
                    if code in NATIVE_CRASH_RETURN_CODES:
                        video["status"] = "failed"
                        state["updated_at"] = utc_now()
                        state["failures"] = run_failures
                        logger.line(f"native crash return_code={code}; stopping runner for clean resume")
                        write_json(state_path, state)
                        return 2
                    if args.stop_on_error:
                        state["failures"] = run_failures
                        write_json(state_path, state)
                        return 2
                    break
                state["updated_at"] = utc_now()
                state["failures"] = run_failures
                write_json(state_path, state)

            if not video_failed:
                video["status"] = "done"
            else:
                video["status"] = "failed"
            state["updated_at"] = utc_now()
            write_json(state_path, state)

            if processed_since_index >= args.index_every:
                build_index(args, root, logger, state, state_path)
                processed_since_index = 0

        build_index(args, root, logger, state, state_path)
        final_summary = summarize(root, entries)
        logger.line(f"final_summary={json.dumps(final_summary, ensure_ascii=False, sort_keys=True)}")
        state["last_summary"] = final_summary
        state["finished_at"] = utc_now()
        state["status"] = "failed" if failures else "done"
        state["failures"] = run_failures
        write_json(state_path, state)
        return 2 if failures else 0
    finally:
        logger.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Unattended cnga full pipeline runner with log/resume.")
    parser.add_argument("--root", default=".", type=Path)
    parser.add_argument("--content-type", default="regular", choices=["regular", "livestream", "short"])
    parser.add_argument("--start-offset", type=int, default=0)
    parser.add_argument("--end-offset", type=int, default=None)
    parser.add_argument("--model-size", default="large-v3")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--compute-type", default="float16")
    parser.add_argument("--beam-size", type=int, default=5)
    parser.add_argument("--vad-filter", action="store_true")
    parser.add_argument("--index-every", type=int, default=5)
    parser.add_argument("--stop-on-error", action="store_true")
    parser.add_argument("--status", action="store_true", help="Print artifact counts and recent failures without running.")
    return parser


if __name__ == "__main__":
    raise SystemExit(run(build_parser().parse_args()))
