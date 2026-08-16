"""Chat local có bằng chứng — phong cách từ index (style), kiến thức từ content.

Cần llama.cpp server (mặc định http://127.0.0.1:8080/completion).
Nếu server không chạy, fallback trích dẫn từ index.

Chạy:
  rtk uv run python scripts/run_chat.py --root H:\\cai-nghien-trading-local-rag

Một câu:
  rtk uv run python scripts/run_chat.py --root H:\\cai-nghien-trading-local-rag -q "Quản lý vốn thế nào?"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _runner_common import load_toml_section, resolve_root


def main() -> int:
    parser = argparse.ArgumentParser(description="Chat local grounded + optional llama.cpp style.")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("-q", "--question", default=None, help="Một câu hỏi rồi thoát.")
    parser.add_argument("--endpoint", default=None, help="llama.cpp completion URL.")
    parser.add_argument("--no-llm", action="store_true", help="Chỉ trích dẫn từ index, không gọi LLM.")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    root = resolve_root(args.root)
    chat_cfg = load_toml_section(root, "chat")
    endpoint = (args.endpoint or chat_cfg.get("llama_endpoint") or "").strip()
    use_llm = not args.no_llm

    from cai_nghien_assistant.chat import answer_question
    from cai_nghien_assistant.paths import configure_local_environment

    configure_local_environment(root)

    def ask(text: str) -> None:
        text = text.strip()
        if not text:
            return
        answer = answer_question(root, text, limit=args.limit, endpoint=endpoint or None, use_llm=use_llm)
        print(answer)
        print()

    if args.question:
        ask(args.question)
        return 0

    print("Chat Trại Cai Nghiện (local). Gõ 'exit' để thoát.", flush=True)
    if use_llm:
        if endpoint:
            print(f"LLM: {endpoint}", flush=True)
        else:
            print("Chưa có endpoint — chỉ chế độ trích dẫn. Sửa [chat].llama_endpoint trong config/project.toml", flush=True)
    else:
        print("Chế độ: trích dẫn index (--no-llm).", flush=True)
    print()

    while True:
        try:
            line = input("Bạn> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if line.lower() in {"exit", "quit", "q"}:
            break
        ask(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
