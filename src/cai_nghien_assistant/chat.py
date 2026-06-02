"""Evidence-grounded chat guardrails."""

from __future__ import annotations

from pathlib import Path

from .config import load_project_config
from .retrieval import SearchIndex, format_timestamp
from .schema import Evidence


UNKNOWN_ANSWER = "Tôi không biết dựa trên dữ liệu đã phân tích từ kênh này."


def source_label(evidence: Evidence) -> str:
    timestamp = format_timestamp(evidence.start)
    suffix = f" @ {timestamp}" if timestamp else ""
    source_kind = "OCR/frame" if evidence.source_type.startswith(("ocr", "vision")) else evidence.source_type
    return f"{evidence.title} ({evidence.published_at}{suffix}, {source_kind})"


def build_grounded_prompt(question: str, content: list[Evidence], style: list[Evidence] | None = None) -> str:
    """Build a prompt for an optional local model.

    The prompt explicitly forbids using style observations as factual evidence.
    """

    evidence_block = "\n".join(
        f"[{idx}] {source_label(item)}\n{item.text}" for idx, item in enumerate(content, start=1)
    )
    style_block = "\n".join(item.text for item in (style or [])[:3])
    return f"""Bạn là trợ lý local cho một corpus YouTube.

Luật bắt buộc:
- Chỉ trả lời bằng thông tin có trong EVIDENCE.
- Nếu EVIDENCE không đủ, trả lời đúng: {UNKNOWN_ANSWER}
- STYLE chỉ dùng để chọn cách diễn đạt, không phải bằng chứng sự thật.
- Không tự nhận là chủ kênh hoặc đại diện chính thức.
- Không tạo nhận định giao dịch mới.
- Mỗi ý kiến thức phải có nguồn [số].

QUESTION:
{question}

EVIDENCE:
{evidence_block}

STYLE:
{style_block}

Trả lời tiếng Việt, ngắn gọn, kèm nguồn.
"""


def build_extractive_answer(question: str, evidence: list[Evidence]) -> str:
    """Safe fallback answer that quotes/paraphrases retrieved evidence only."""

    if not evidence:
        return UNKNOWN_ANSWER

    lines = ["Dựa trên dữ liệu đã phân tích từ kênh này:"]
    for idx, item in enumerate(evidence, start=1):
        text = item.text.strip()
        if len(text) > 500:
            text = text[:497].rstrip() + "..."
        lines.append(f"- [{idx}] {text}")

    lines.append("")
    lines.append("Nguồn:")
    for idx, item in enumerate(evidence, start=1):
        lines.append(f"[{idx}] {source_label(item)}")
    return "\n".join(lines)


def answer_question(root: str | Path | None, question: str, limit: int | None = None) -> str:
    config = load_project_config(root)
    index = SearchIndex.from_project(root)
    try:
        content_limit = limit or int(config["retrieval"]["default_limit"])
        evidence = index.search(question, kind="content", limit=content_limit)
        if len(evidence) < int(config["retrieval"]["min_content_evidence"]):
            return config["guardrails"]["unknown_answer"]
        return build_extractive_answer(question, evidence)
    finally:
        index.close()

