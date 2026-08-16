"""Command line entry point."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .analyzer import run_local_analysis
from .asr import asr_batch
from .chat import answer_question
from .chroma_index import build_chroma_index
from .config import load_project_config
from .frames import extract_frames_batch, ocr_frames_batch
from .knowledge import build_knowledge_chunks
from .knowledge_extraction.batch import run_extract_batch
from .playbook.ask import ask_playbook
from .playbook.assemble import assemble_video_sources
from .playbook.compile import run_compile_playbook
from .playbook.pages import export_playbook_pages
from .media import fetch_audio_batch, fetch_video_light_batch
from .paths import NON_PATH_ENV_KEYS, configure_local_environment, ensure_project_tree, resolve_project_root
from .retrieval import SearchIndex
from .transcript_quality.batch import run_clean_batch
from .transcript_quality.review_ui import serve_review_ui
from .transcripts import normalize_all_transcripts
from .youtube_collect import collect, fetch_oldest_sidecars


def cmd_init(args: argparse.Namespace) -> int:
    root = resolve_project_root(args.root)
    env = configure_local_environment(root)
    ensure_project_tree(root)
    print(f"Initialized project tree: {root}")
    print(json.dumps(env, ensure_ascii=False, indent=2))
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    root = resolve_project_root(args.root)
    env = configure_local_environment(root)
    config = load_project_config(root)
    print(f"Project root: {root}")
    print(f"Channel: {config['channel']['url']}")
    for key, value in sorted(env.items()):
        if key in NON_PATH_ENV_KEYS:
            print(f"{key}={value}")
            continue
        inside = Path(value).resolve() == root or root in Path(value).resolve().parents
        print(f"{key}={value} inside_project={inside}")
    return 0


def cmd_collect(args: argparse.Namespace) -> int:
    entries = collect(
        root=args.root,
        limit=args.limit,
        fetch_sidecars=args.fetch_sidecars,
        sidecar_limit=args.sidecar_limit,
        enrich_metadata=not args.no_enrich_metadata,
    )
    print(f"Collected catalog entries: {len(entries)}")
    counts: dict[str, int] = {}
    for entry in entries:
        counts[entry["content_type"]] = counts.get(entry["content_type"], 0) + 1
    print(json.dumps(counts, ensure_ascii=False, sort_keys=True))
    return 0


def cmd_fetch_sidecars(args: argparse.Namespace) -> int:
    manifests = fetch_oldest_sidecars(args.root, limit=args.limit, content_type=args.content_type)
    print(f"Fetched sidecar manifests: {len(manifests)}")
    return 0


def cmd_fetch_audio(args: argparse.Namespace) -> int:
    manifests = fetch_audio_batch(args.root, limit=args.limit, content_type=args.content_type, offset=args.offset, force=args.force)
    print(f"Fetched audio manifests: {len(manifests)}")
    return 0


def cmd_fetch_video_light(args: argparse.Namespace) -> int:
    manifests = fetch_video_light_batch(args.root, limit=args.limit, content_type=args.content_type, offset=args.offset, force=args.force)
    print(f"Fetched video-light manifests: {len(manifests)}")
    return 0


def cmd_asr(args: argparse.Namespace) -> int:
    result = asr_batch(
        args.root,
        limit=args.limit,
        content_type=args.content_type,
        offset=args.offset,
        model_size=args.model_size,
        device=args.device,
        compute_type=args.compute_type,
        beam_size=args.beam_size,
        vad_filter=args.vad_filter,
        force=args.force,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_extract_frames(args: argparse.Namespace) -> int:
    result = extract_frames_batch(
        args.root,
        limit=args.limit,
        content_type=args.content_type,
        offset=args.offset,
        scene_threshold=args.scene_threshold,
        max_frames=args.max_frames,
        force=args.force,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_ocr_frames(args: argparse.Namespace) -> int:
    result = ocr_frames_batch(
        args.root,
        limit=args.limit,
        content_type=args.content_type,
        offset=args.offset,
        force=args.force,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_normalize_transcripts(args: argparse.Namespace) -> int:
    result = normalize_all_transcripts(args.root, limit=args.limit, content_type=args.content_type)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_clean_transcripts(args: argparse.Namespace) -> int:
    result = run_clean_batch(
        args.root,
        limit=args.limit,
        content_type=args.content_type,
        offset=args.offset,
        model_id=args.model_id,
        engine=args.engine,
        endpoint=args.endpoint,
        force=args.force,
        pause_file=args.pause_file,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_review_ui(args: argparse.Namespace) -> int:
    serve_review_ui(args.root, host=args.host, port=args.port)
    return 0


def cmd_assemble_playbook_source(args: argparse.Namespace) -> int:
    result = assemble_video_sources(args.root, limit=args.limit, force=args.force)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_compile_playbook(args: argparse.Namespace) -> int:
    result = run_compile_playbook(
        args.root,
        limit=args.limit,
        force=args.force,
        endpoint=args.endpoint,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_export_pages(args: argparse.Namespace) -> int:
    result = export_playbook_pages(args.root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    print(ask_playbook(args.root, args.question))
    return 0


def cmd_extract_knowledge(args: argparse.Namespace) -> int:
    result = run_extract_batch(
        args.root,
        limit=args.limit,
        content_type=args.content_type,
        force=args.force,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_build_index(args: argparse.Namespace) -> int:
    chunks = build_knowledge_chunks(args.root)
    index = SearchIndex.from_project(args.root)
    try:
        changed = index.replace_chunks(chunks)
        print(f"Chunks prepared: {len(chunks)}")
        print(f"Chunks indexed: {changed}")
        print(f"Total chunks indexed: {index.count_chunks()}")
    finally:
        index.close()
    return 0


def cmd_build_chroma(args: argparse.Namespace) -> int:
    chunks = build_knowledge_chunks(args.root)
    count = build_chroma_index(args.root, chunks)
    print(f"Chunks upserted to Chroma: {count}")
    return 0


def cmd_chat(args: argparse.Namespace) -> int:
    print(answer_question(args.root, args.question, args.limit))
    return 0


def cmd_analyze_local(args: argparse.Namespace) -> int:
    if not args.endpoint:
        raise SystemExit("Need --endpoint for local llama.cpp server, e.g. http://127.0.0.1:8080/completion")
    chunks = build_knowledge_chunks(args.root)
    result = run_local_analysis(args.root, chunks, endpoint=args.endpoint, model_id=args.model_id, limit=args.limit)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cnga", description="Local YouTube knowledge playbook pipeline.")
    parser.add_argument("--root", default=".", help="Project root. Defaults to current directory.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create local project runtime directories.")
    init_parser.set_defaults(func=cmd_init)

    doctor_parser = subparsers.add_parser("doctor", help="Check local paths and cache env.")
    doctor_parser.set_defaults(func=cmd_doctor)

    collect_parser = subparsers.add_parser("collect", help="Collect channel catalog and optional sidecars.")
    collect_parser.add_argument("--limit", type=int, default=None)
    collect_parser.add_argument("--fetch-sidecars", action="store_true")
    collect_parser.add_argument("--sidecar-limit", type=int, default=None, help="Fetch sidecars only for the first N oldest entries.")
    collect_parser.add_argument("--no-enrich-metadata", action="store_true", help="Skip per-video metadata fetch.")
    collect_parser.set_defaults(func=cmd_collect)

    sidecars_parser = subparsers.add_parser("fetch-sidecars", help="Fetch sidecars from latest dated catalog, oldest first.")
    sidecars_parser.add_argument("--limit", type=int, default=None)
    sidecars_parser.add_argument("--content-type", choices=["regular", "livestream", "short"], default=None)
    sidecars_parser.set_defaults(func=cmd_fetch_sidecars)

    audio_parser = subparsers.add_parser("fetch-audio", help="Fetch audio-only media from latest catalog, oldest first.")
    audio_parser.add_argument("--limit", type=int, default=None)
    audio_parser.add_argument("--offset", type=int, default=0)
    audio_parser.add_argument("--content-type", choices=["regular", "livestream", "short"], default=None)
    audio_parser.add_argument("--force", action="store_true")
    audio_parser.set_defaults(func=cmd_fetch_audio)

    video_parser = subparsers.add_parser("fetch-video-light", help="Fetch video-only light media for frame/OCR analysis.")
    video_parser.add_argument("--limit", type=int, default=None)
    video_parser.add_argument("--offset", type=int, default=0)
    video_parser.add_argument("--content-type", choices=["regular", "livestream", "short"], default=None)
    video_parser.add_argument("--force", action="store_true")
    video_parser.set_defaults(func=cmd_fetch_video_light)

    asr_parser = subparsers.add_parser("asr", help="Run local ASR on fetched audio.")
    asr_parser.add_argument("--limit", type=int, default=None)
    asr_parser.add_argument("--offset", type=int, default=0)
    asr_parser.add_argument("--content-type", choices=["regular", "livestream", "short"], default=None)
    asr_parser.add_argument("--model-size", default="large-v3")
    asr_parser.add_argument("--device", default="cuda")
    asr_parser.add_argument("--compute-type", default="float16")
    asr_parser.add_argument("--beam-size", type=int, default=5)
    asr_parser.add_argument("--vad-filter", action="store_true", help="Enable VAD. Off by default because it removed speech on some YouTube audio.")
    asr_parser.add_argument("--force", action="store_true")
    asr_parser.set_defaults(func=cmd_asr)

    frames_parser = subparsers.add_parser("extract-frames", help="Extract sparse scene frames from fetched video-light files.")
    frames_parser.add_argument("--limit", type=int, default=None)
    frames_parser.add_argument("--offset", type=int, default=0)
    frames_parser.add_argument("--content-type", choices=["regular", "livestream", "short"], default=None)
    frames_parser.add_argument("--scene-threshold", type=float, default=None)
    frames_parser.add_argument("--max-frames", type=int, default=None)
    frames_parser.add_argument("--force", action="store_true")
    frames_parser.set_defaults(func=cmd_extract_frames)

    ocr_parser = subparsers.add_parser("ocr-frames", help="Run project-local PaddleOCR on extracted frames.")
    ocr_parser.add_argument("--limit", type=int, default=None)
    ocr_parser.add_argument("--offset", type=int, default=0)
    ocr_parser.add_argument("--content-type", choices=["regular", "livestream", "short"], default=None)
    ocr_parser.add_argument("--force", action="store_true")
    ocr_parser.set_defaults(func=cmd_ocr_frames)

    transcripts_parser = subparsers.add_parser("normalize-transcripts", help="Normalize YouTube subtitle sidecars.")
    transcripts_parser.add_argument("--limit", type=int, default=None)
    transcripts_parser.add_argument("--content-type", choices=["regular", "livestream", "short"], default=None)
    transcripts_parser.set_defaults(func=cmd_normalize_transcripts)

    clean_defaults = load_project_config()
    tq = clean_defaults.get("transcript_quality") or {}
    default_model = str(tq.get("default_model_id") or "conservative-refine")
    default_engine = str(tq.get("default_engine") or default_model)

    clean_parser = subparsers.add_parser(
        "clean-transcripts",
        help="Conservative transcript clean (raw→ai_cleaned→approved), no general LLM by default.",
    )
    clean_parser.add_argument("--limit", type=int, default=None)
    clean_parser.add_argument("--offset", type=int, default=0)
    clean_parser.add_argument("--content-type", choices=["regular", "livestream", "short"], default=None)
    clean_parser.add_argument(
        "--model-id",
        default=default_model,
        help="Stored in ai_cleaned.meta (e.g. conservative-refine, rule-only, asr-reprocess).",
    )
    clean_parser.add_argument(
        "--engine",
        default=default_engine,
        choices=["conservative-refine", "rule-only", "asr-reprocess", "llm"],
        help="Cleaning engine. Default: conservative-refine (rules+glossary+confusion map).",
    )
    clean_parser.add_argument(
        "--endpoint",
        default=None,
        help="LEGACY: llama.cpp URL for engine=llm only. Không khuyến nghị — chất lượng kém, dễ viết lại.",
    )
    clean_parser.add_argument(
        "--force",
        action="store_true",
        help="Re-run when raw hash/logic/model match; skips videos already approved unless you reset review first.",
    )
    clean_parser.add_argument("--pause-file", default=None)
    clean_parser.set_defaults(func=cmd_clean_transcripts)

    review_parser = subparsers.add_parser("review-ui", help="Local web UI for transcript review.")
    review_parser.add_argument("--host", default="127.0.0.1")
    review_parser.add_argument("--port", type=int, default=8765)
    review_parser.set_defaults(func=cmd_review_ui)

    assemble_playbook_parser = subparsers.add_parser(
        "assemble-playbook-source",
        help="Gom lời từng video thành một file nguồn đủ ý (không cắt câu).",
    )
    assemble_playbook_parser.add_argument("--limit", type=int, default=None)
    assemble_playbook_parser.add_argument("--force", action="store_true")
    assemble_playbook_parser.set_defaults(func=cmd_assemble_playbook_source)

    compile_playbook_parser = subparsers.add_parser(
        "compile-playbook",
        help="Video mới: viết bài (cần --endpoint) rồi gắn thêm vào chương, không viết lại cả sách.",
    )
    compile_playbook_parser.add_argument("--limit", type=int, default=None)
    compile_playbook_parser.add_argument("--force", action="store_true")
    compile_playbook_parser.add_argument(
        "--endpoint",
        default=None,
        help="llama.cpp local URL, ví dụ http://127.0.0.1:8080/completion",
    )
    compile_playbook_parser.set_defaults(func=cmd_compile_playbook)

    export_pages_parser = subparsers.add_parser(
        "export-pages",
        help="Xuất sách ra docs/ để bật GitHub Pages (đọc + ô hỏi).",
    )
    export_pages_parser.set_defaults(func=cmd_export_pages)

    ask_parser = subparsers.add_parser(
        "ask",
        help="Hỏi kiến thức: đưa nguyên chương liên quan, không ghép mảnh.",
    )
    ask_parser.add_argument("question")
    ask_parser.set_defaults(func=cmd_ask)

    extract_parser = subparsers.add_parser(
        "extract-knowledge",
        help="[Cũ] Cắt câu thành fact. Không dùng để trả lời. Dùng cnga ask / playbook.",
    )
    extract_parser.add_argument("--limit", type=int, default=None)
    extract_parser.add_argument("--content-type", choices=["regular", "livestream", "short", "regular+livestream"], default=None)
    extract_parser.add_argument("--force", action="store_true", help="Re-write per-video facts even if facts.jsonl exists.")
    extract_parser.set_defaults(func=cmd_extract_knowledge)

    index_parser = subparsers.add_parser("build-index", help="[Optional] Build/update local FTS search index.")
    index_parser.set_defaults(func=cmd_build_index)

    chroma_parser = subparsers.add_parser("build-chroma", help="Build/update optional project-local Chroma index.")
    chroma_parser.set_defaults(func=cmd_build_chroma)

    chat_parser = subparsers.add_parser("chat", help="[Deprecated] Local chat — quality thấp, dùng extract-knowledge thay thế.")
    chat_parser.add_argument("question")
    chat_parser.add_argument("--limit", type=int, default=None)
    chat_parser.set_defaults(func=cmd_chat)

    analyze_parser = subparsers.add_parser("analyze-local", help="[Optional] LLM batch extraction — cần llama.cpp, chất lượng tùy model.")
    analyze_parser.add_argument("--endpoint", default=None)
    analyze_parser.add_argument("--model-id", default="llama.cpp-local")
    analyze_parser.add_argument("--limit", type=int, default=None)
    analyze_parser.set_defaults(func=cmd_analyze_local)

    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
