"""Rejoin ASR segments before treating speech as sentences."""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Iterable

from .schema import TranscriptSegment


_SENTENCE_BOUNDARY = re.compile(r"[.!?…][\"'”’)]*\s+")
_SENTENCE_END = re.compile(r"[.!?…][\"'”’)]*$")


def _sentence_parts(text: str) -> list[str]:
    parts: list[str] = []
    start = 0
    for match in _SENTENCE_BOUNDARY.finditer(text):
        parts.append(text[start:match.end()].strip())
        start = match.end()
    parts.append(text[start:].strip())
    return [part for part in parts if part]


def sentence_spans(segments: Iterable[TranscriptSegment]) -> list[TranscriptSegment]:
    """Return complete sentences with the first and last ASR segment times.

    Missing punctuation leaves one longer span for review; it is never split
    merely to meet a character limit.
    """

    spans: list[TranscriptSegment] = []
    first: TranscriptSegment | None = None
    end = 0.0
    pieces: list[str] = []

    def flush() -> None:
        nonlocal first, pieces
        if first is not None and pieces:
            spans.append(replace(first, end=end, text=" ".join(pieces)))
        first = None
        pieces = []

    for segment in segments:
        text = segment.text.strip()
        if not text:
            continue
        if first is not None and segment.video_id != first.video_id:
            flush()
        for part in _sentence_parts(text):
            if first is None:
                first = segment
            pieces.append(part)
            end = segment.end
            if _SENTENCE_END.search(part):
                flush()
    flush()
    return spans
