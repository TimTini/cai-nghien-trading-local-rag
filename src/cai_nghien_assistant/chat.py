"""Evidence-grounded chat guardrails."""

from __future__ import annotations

from pathlib import Path

from .config import load_project_config
from .retrieval import SearchIndex, format_timestamp, query_terms
from .schema import Evidence


UNKNOWN_ANSWER = "Tôi không biết dựa trên dữ liệu đã phân tích từ kênh này."

QUESTION_STOP_TERMS = {
    "anh",
    "bao",
    "bạn",
    "cho",
    "có",
    "của",
    "đâu",
    "đây",
    "đó",
    "được",
    "gì",
    "giải",
    "hỏi",
    "kênh",
    "không",
    "là",
    "mình",
    "một",
    "nào",
    "này",
    "như",
    "nói",
    "ra",
    "sao",
    "thế",
    "thích",
    "trả",
    "trong",
    "trên",
    "và",
    "về",
    "với",
}

DOMAIN_TERMS = {
    "btc",
    "bitcoin",
    "bot",
    "crypto",
    "dca",
    "future",
    "futures",
    "giao",
    "long",
    "okx",
    "short",
    "trade",
    "trading",
}


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


def meaningful_question_terms(question: str) -> list[str]:
    """Return query terms that should be supported by the retrieved evidence."""

    return [term for term in query_terms(question) if term not in QUESTION_STOP_TERMS]


def required_relevance_hits(terms: list[str]) -> int:
    return max(2, min(len(terms), (len(terms) + 1) // 2))


def evidence_hit_count(item: Evidence, terms: list[str]) -> int:
    haystack = f"{item.title} {item.text}".lower()
    return sum(1 for term in terms if term in haystack)


def filter_relevant_evidence(question: str, evidence: list[Evidence]) -> list[Evidence]:
    terms = meaningful_question_terms(question)
    if not terms:
        return []
    if len(terms) == 1:
        only_term = terms[0]
        if only_term not in DOMAIN_TERMS:
            return []
        return [item for item in evidence if evidence_hit_count(item, terms) >= 1]

    required_hits = required_relevance_hits(terms)
    return [item for item in evidence if evidence_hit_count(item, terms) >= required_hits]


def has_enough_content_relevance(question: str, evidence: list[Evidence]) -> bool:
    """Reject weak OR-match retrieval that only hits incidental transcript words."""

    terms = meaningful_question_terms(question)
    if not terms or not evidence:
        return False
    if len(terms) == 1:
        only_term = terms[0]
        return only_term in DOMAIN_TERMS and any(
            only_term in f"{item.title} {item.text}".lower() for item in evidence
        )

    required_hits = required_relevance_hits(terms)
    covered_terms: set[str] = set()
    strongest_single_evidence = 0
    for item in evidence:
        haystack = f"{item.title} {item.text}".lower()
        hits = {term for term in terms if term in haystack}
        covered_terms.update(hits)
        strongest_single_evidence = max(strongest_single_evidence, len(hits))

    return strongest_single_evidence >= required_hits and len(covered_terms) >= required_hits


def answer_question(root: str | Path | None, question: str, limit: int | None = None) -> str:
    config = load_project_config(root)
    index = SearchIndex.from_project(root)
    try:
        content_limit = limit or int(config["retrieval"]["default_limit"])
        evidence = index.search(question, kind="content", limit=content_limit)
        relevant_evidence = filter_relevant_evidence(question, evidence)
        if len(relevant_evidence) < int(config["retrieval"]["min_content_evidence"]) or not has_enough_content_relevance(
            question, evidence
        ):
            return config["guardrails"]["unknown_answer"]
        return build_extractive_answer(question, relevant_evidence)
    finally:
        index.close()
