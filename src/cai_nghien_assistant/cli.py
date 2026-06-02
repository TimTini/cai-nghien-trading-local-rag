"""Command line entry point."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .analyzer import run_local_analysis
from .chat import answer_question
from .chroma_index import build_chroma_index
from .config import load_project_config
from .knowledge import build_knowledge_chunks
from .paths import configure_local_environment, ensure_project_tree, resolve_project_root
from .retrieval import SearchIndex
from .transcripts import normalize_all_transcripts
from .youtube_collect import collect


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
        inside = Path(value).resolve() == root or root in Path(value).resolve().parents
        print(f"{key}={value} inside_project={inside}")
    return 0


def cmd_collect(args: argparse.Namespace) -> int:
    entries = collect(root=args.root, limit=args.limit, fetch_sidecars=args.fetch_sidecars)
    print(f"Collected catalog entries: {len(entries)}")
    counts: dict[str, int] = {}
    for entry in entries:
        counts[entry["content_type"]] = counts.get(entry["content_type"], 0) + 1
    print(json.dumps(counts, ensure_ascii=False, sort_keys=True))
    return 0


def cmd_normalize_transcripts(args: argparse.Namespace) -> int:
    result = normalize_all_transcripts(args.root)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def cmd_build_index(args: argparse.Namespace) -> int:
    chunks = build_knowledge_chunks(args.root)
    index = SearchIndex.from_project(args.root)
    try:
        changed = index.upsert_chunks(chunks)
        print(f"Chunks prepared: {len(chunks)}")
        print(f"New chunks indexed: {changed}")
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
    parser = argparse.ArgumentParser(prog="cnga", description="Local evidence-grounded YouTube RAG pipeline.")
    parser.add_argument("--root", default=".", help="Project root. Defaults to current directory.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create local project runtime directories.")
    init_parser.set_defaults(func=cmd_init)

    doctor_parser = subparsers.add_parser("doctor", help="Check local paths and cache env.")
    doctor_parser.set_defaults(func=cmd_doctor)

    collect_parser = subparsers.add_parser("collect", help="Collect channel catalog and optional sidecars.")
    collect_parser.add_argument("--limit", type=int, default=None)
    collect_parser.add_argument("--fetch-sidecars", action="store_true")
    collect_parser.set_defaults(func=cmd_collect)

    transcripts_parser = subparsers.add_parser("normalize-transcripts", help="Normalize YouTube subtitle sidecars.")
    transcripts_parser.set_defaults(func=cmd_normalize_transcripts)

    index_parser = subparsers.add_parser("build-index", help="Build/update local retrieval index.")
    index_parser.set_defaults(func=cmd_build_index)

    chroma_parser = subparsers.add_parser("build-chroma", help="Build/update optional project-local Chroma index.")
    chroma_parser.set_defaults(func=cmd_build_chroma)

    chat_parser = subparsers.add_parser("chat", help="Ask a question with evidence retrieval.")
    chat_parser.add_argument("question")
    chat_parser.add_argument("--limit", type=int, default=None)
    chat_parser.set_defaults(func=cmd_chat)

    analyze_parser = subparsers.add_parser("analyze-local", help="Run reusable local LLM extraction with cache.")
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
