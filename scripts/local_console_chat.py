"""Repo-local GGUF console chatbot.

It loads a GGUF model from this project and uses the existing local RAG index as
the factual source. It does not require Ollama Desktop or an Ollama server.

Usage:
  rtk uv run --extra chat python scripts/local_console_chat.py --root H:\\test
  rtk uv run --extra chat python scripts/local_console_chat.py --root H:\\test -q "Bot DCA trên OKX là gì?"
"""

from __future__ import annotations

import argparse
import os
import sys
import tomllib
from pathlib import Path
from typing import Any


DEFAULT_CONFIG = Path("config/local_chat_model.toml")
UNKNOWN_FALLBACK = "Tôi không biết dựa trên dữ liệu đã phân tích từ kênh này."


def configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="replace")


def ensure_project_imports(root: Path) -> None:
    src = root / "src"
    if src.exists():
        sys.path.insert(0, str(src))


def load_config(root: Path, config_path: Path) -> dict[str, Any]:
    full_path = config_path if config_path.is_absolute() else root / config_path
    if not full_path.exists():
        raise FileNotFoundError(f"Missing config: {full_path}")
    with full_path.open("rb") as handle:
        return tomllib.load(handle)


def project_path(root: Path, relative_path: str) -> Path:
    candidate = (root / relative_path).resolve()
    root_resolved = root.resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(f"Path escapes project root: {candidate}") from exc
    return candidate


def configured_model_path(root: Path, config: dict[str, Any]) -> Path:
    model_cfg = config["model"]
    return project_path(root, str(model_cfg["relative_dir"])) / str(model_cfg["filename"])


def load_llm(model_path: Path, runtime_cfg: dict[str, Any]):
    # Some local tools set CUDA_PATH to a private runtime that may no longer
    # exist. llama-cpp-python checks CUDA_PATH during import, so remove only
    # invalid values and keep valid CUDA installs intact.
    cuda_path = os.environ.get("CUDA_PATH")
    if cuda_path and not (Path(cuda_path) / "lib").exists():
        os.environ.pop("CUDA_PATH", None)

    try:
        from llama_cpp import Llama
    except ImportError as exc:
        raise RuntimeError("Missing dependency llama_cpp. Run: rtk uv sync --extra chat") from exc

    n_threads = int(runtime_cfg.get("n_threads") or 0) or (os.cpu_count() or 4)
    return Llama(
        model_path=str(model_path),
        n_ctx=int(runtime_cfg.get("n_ctx", 8192)),
        n_threads=n_threads,
        n_gpu_layers=int(runtime_cfg.get("n_gpu_layers", 0)),
        verbose=False,
    )


def evidence_date_key(item: Any) -> tuple[str, float]:
    return (str(getattr(item, "published_at", "") or ""), float(getattr(item, "start", 0.0) or 0.0))


def retrieve_relevant_evidence(root: Path, question: str, config: dict[str, Any]) -> tuple[list[Any], list[Any], str]:
    from cai_nghien_assistant.chat import (
        filter_relevant_evidence,
        has_enough_content_relevance,
        retrieve_evidence,
    )
    from cai_nghien_assistant.config import load_project_config

    project_cfg = load_project_config(root)
    unknown_answer = str(project_cfg.get("guardrails", {}).get("unknown_answer") or UNKNOWN_FALLBACK)
    rag_cfg = config.get("rag", {})
    pool_limit = int(rag_cfg.get("pool_limit", 30))
    style_limit = int(rag_cfg.get("style_limit", 3))
    keep_limit = int(rag_cfg.get("limit", 8))
    min_evidence = int(rag_cfg.get("min_content_evidence", 1))

    content, style = retrieve_evidence(root, question, content_limit=pool_limit, style_limit=style_limit)
    relevant = filter_relevant_evidence(question, content)
    if len(relevant) < min_evidence or not has_enough_content_relevance(question, content):
        return [], style, unknown_answer

    if bool(rag_cfg.get("prefer_newest", True)):
        relevant = sorted(relevant, key=evidence_date_key, reverse=True)
    return relevant[:keep_limit], style, unknown_answer


def build_messages(question: str, evidence: list[Any], style: list[Any], history: list[dict[str, str]]) -> list[dict[str, str]]:
    from cai_nghien_assistant.chat import source_label

    evidence_block = "\n\n".join(
        f"[{idx}] {source_label(item)}\n{item.text}" for idx, item in enumerate(evidence, start=1)
    )
    style_block = "\n".join(item.text for item in style[:3])
    system = """Bạn là chatbot local cho corpus YouTube của dự án.

Luật bắt buộc:
- Chỉ dùng EVIDENCE làm bằng chứng sự thật.
- HISTORY chỉ để hiểu ngữ cảnh hội thoại, không phải bằng chứng sự thật.
- Nếu EVIDENCE không đủ, trả lời đúng: Tôi không biết dựa trên dữ liệu đã phân tích từ kênh này.
- Nếu cùng một thông tin xuất hiện ở nhiều mốc thời gian hoặc bị mâu thuẫn, ưu tiên EVIDENCE có published_at mới nhất; bỏ qua dữ liệu cũ hơn.
- Không tự nhận là chủ kênh hoặc đại diện chính thức.
- Không tạo khuyến nghị giao dịch mới ngoài dữ liệu.
- Mỗi ý kiến thức phải kèm nguồn [số].
- Trả lời tiếng Việt, ngắn gọn."""

    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    messages.extend(history)
    messages.append(
        {
            "role": "user",
            "content": (
                f"QUESTION:\n{question}\n\n"
                f"EVIDENCE (đã sắp xếp mới nhất trước):\n{evidence_block}\n\n"
                f"STYLE (chỉ để chọn cách diễn đạt, không dùng làm sự thật):\n{style_block}\n\n"
                "Hãy trả lời theo luật."
            ),
        }
    )
    return messages


def generate_answer(llm: Any, messages: list[dict[str, str]], runtime_cfg: dict[str, Any]) -> str:
    result = llm.create_chat_completion(
        messages=messages,
        temperature=float(runtime_cfg.get("temperature", 0.3)),
        top_p=float(runtime_cfg.get("top_p", 0.8)),
        top_k=int(runtime_cfg.get("top_k", 20)),
        repeat_penalty=float(runtime_cfg.get("repeat_penalty", 1.1)),
        max_tokens=int(runtime_cfg.get("max_tokens", 900)),
    )
    return str(result["choices"][0]["message"]["content"]).strip()


def answer_once(llm: Any, root: Path, question: str, config: dict[str, Any], history: list[dict[str, str]]) -> str:
    evidence, style, unknown_answer = retrieve_relevant_evidence(root, question, config)
    if not evidence:
        return unknown_answer
    messages = build_messages(question, evidence, style, history)
    answer = generate_answer(llm, messages, config.get("runtime", {}))
    return answer or unknown_answer


def main() -> int:
    configure_stdio()
    parser = argparse.ArgumentParser(description="Repo-local GGUF console chatbot.")
    parser.add_argument("--root", type=Path, default=Path("."), help="Project root.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="Model config TOML.")
    parser.add_argument("--model", type=Path, default=None, help="Override GGUF model path.")
    parser.add_argument("-q", "--question", default=None, help="Ask one question then exit.")
    parser.add_argument("--history-turns", type=int, default=2, help="Number of previous turns to keep.")
    args = parser.parse_args()

    root = args.root.resolve()
    ensure_project_imports(root)
    config = load_config(root, args.config)
    model_path = args.model.resolve() if args.model else configured_model_path(root, config)
    if not model_path.exists():
        print(f"Missing model: {model_path}", file=sys.stderr)
        print(
            "Download with: rtk uv run --extra chat python scripts/download_local_chat_model.py --root "
            f"{root}",
            file=sys.stderr,
        )
        return 2

    llm = load_llm(model_path, config.get("runtime", {}))
    history: list[dict[str, str]] = []

    def ask(text: str) -> None:
        nonlocal history
        text = text.strip()
        if not text:
            return
        answer = answer_once(llm, root, text, config, history)
        print(f"Bot> {answer}\n", flush=True)
        history.extend([{"role": "user", "content": text}, {"role": "assistant", "content": answer}])
        keep = max(args.history_turns, 0) * 2
        if keep:
            history = history[-keep:]
        else:
            history = []

    if args.question:
        ask(args.question)
        return 0

    print("Chat local GGUF. Gõ 'exit' để thoát.", flush=True)
    print(f"Model: {model_path}", flush=True)
    print("Fact rule: nếu trùng/mâu thuẫn theo thời gian, dùng evidence mới nhất.", flush=True)
    while True:
        try:
            line = input("Bạn> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if line.strip().lower() in {"exit", "quit", "q"}:
            break
        ask(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
