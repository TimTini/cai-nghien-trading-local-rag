"""Rule-based fact extraction from cleaned transcripts and OCR."""

from __future__ import annotations

import re
from pathlib import Path

from ..config import load_project_config
from ..knowledge import iter_ocr_chunks
from ..schema import TranscriptSegment
from ..storage import sha256_text
from ..transcript_quality.batch import load_glossary_terms
from .schema import KnowledgeFact

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+")
GARBAGE_CHARS_RE = re.compile(r"[\uFFFD\u200b\u00ad\u0000-\u001f]")

BASE_DOMAIN_TERMS = {
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
    "stop",
    "trade",
    "trading",
    "vốn",
    "rủi ro",
    "lệnh",
    "margin",
    "leverage",
    "đòn bẩy",
    "take profit",
    "stop loss",
}

GUIDANCE_RE = re.compile(
    r"\b(nên|không nên|tránh|phải|luôn|tuyệt đối|đừng|cần|khuyên|gợi ý)\b",
    re.IGNORECASE,
)
DEFINITION_RE = re.compile(
    r"\b(là|được hiểu là|nghĩa là|tức là|khái niệm)\b",
    re.IGNORECASE,
)
METRIC_RE = re.compile(r"\d|%|usd|usdt", re.IGNORECASE)


def domain_terms(root: Path) -> set[str]:
    terms = {t.lower() for t in BASE_DOMAIN_TERMS}
    for term in load_glossary_terms(root):
        cleaned = term.strip().lower()
        if len(cleaned) >= 2:
            terms.add(cleaned)
    return terms


def split_sentences(text: str) -> list[str]:
    parts = SENTENCE_SPLIT_RE.split(text.strip())
    return [part.strip() for part in parts if part.strip()]


def sentence_has_domain_term(sentence: str, terms: set[str]) -> bool:
    lowered = sentence.lower()
    return any(term in lowered for term in terms)


def classify_sentence(sentence: str) -> str:
    if METRIC_RE.search(sentence):
        return "metric"
    if GUIDANCE_RE.search(sentence):
        return "guidance"
    if DEFINITION_RE.search(sentence):
        return "definition"
    return "observation"


def is_usable_sentence(sentence: str, *, min_chars: int) -> bool:
    if len(sentence) < min_chars:
        return False
    if GARBAGE_CHARS_RE.search(sentence):
        return False
    words = sentence.split()
    return len(words) >= 4


def make_fact_id(video_id: str, start: float | None, quote: str) -> str:
    return sha256_text(f"{video_id}|{start}|{quote}")[:20]


def facts_from_segment(
    segment: TranscriptSegment,
    *,
    terms: set[str],
    pipeline_version: str,
    min_chars: int,
    require_domain_term: bool,
) -> list[KnowledgeFact]:
    facts: list[KnowledgeFact] = []
    seen: set[str] = set()
    for sentence in split_sentences(segment.text):
        if not is_usable_sentence(sentence, min_chars=min_chars):
            continue
        if require_domain_term and not sentence_has_domain_term(sentence, terms):
            continue
        fact_id = make_fact_id(segment.video_id, segment.start, sentence)
        if fact_id in seen:
            continue
        seen.add(fact_id)
        facts.append(
            KnowledgeFact(
                fact_id=fact_id,
                video_id=segment.video_id,
                title=segment.title,
                published_at=segment.published_at,
                start=segment.start,
                end=segment.end,
                fact_text=sentence,
                evidence_quote=sentence,
                category=classify_sentence(sentence),
                source_type=segment.source_type,
                source_path=segment.source_path,
                pipeline_version=pipeline_version,
            )
        )
    return facts


def facts_from_segments(
    segments: list[TranscriptSegment],
    root: Path,
    *,
    min_chars: int = 20,
    require_domain_term: bool = True,
) -> list[KnowledgeFact]:
    config = load_project_config(root)
    pipeline_version = config["pipeline"]["version"]
    terms = domain_terms(root)
    facts: list[KnowledgeFact] = []
    for segment in segments:
        facts.extend(
            facts_from_segment(
                segment,
                terms=terms,
                pipeline_version=pipeline_version,
                min_chars=min_chars,
                require_domain_term=require_domain_term,
            )
        )
    return facts


def facts_from_ocr(root: Path) -> list[KnowledgeFact]:
    config = load_project_config(root)
    pipeline_version = config["pipeline"]["version"]
    facts: list[KnowledgeFact] = []
    for chunk in iter_ocr_chunks(root):
        text = chunk.text.removeprefix("OCR màn hình: ").strip()
        if len(text) < 3:
            continue
        fact_id = make_fact_id(chunk.video_id, chunk.start, text)
        facts.append(
            KnowledgeFact(
                fact_id=fact_id,
                video_id=chunk.video_id,
                title=chunk.title,
                published_at=chunk.published_at,
                start=chunk.start,
                end=chunk.end,
                fact_text=text,
                evidence_quote=text,
                category="screen_text",
                source_type=chunk.source_type,
                source_path=chunk.source_path,
                pipeline_version=pipeline_version,
            )
        )
    return facts
