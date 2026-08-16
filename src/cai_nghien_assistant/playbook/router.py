"""Pick playbook chapters by topic keywords. Return whole chapters, not fragments."""

from __future__ import annotations

import re

from .schema import Chapter

SHORT_KEYWORD_RE_TEMPLATE = r"(?<![a-zà-ỹ0-9]){needle}(?![a-zà-ỹ0-9])"


def keyword_in_question(needle: str, lowered: str) -> bool:
    if len(needle) <= 3:
        pattern = SHORT_KEYWORD_RE_TEMPLATE.format(needle=re.escape(needle))
        return re.search(pattern, lowered) is not None
    return needle in lowered


def chapter_score(question: str, chapter: Chapter) -> int:
    lowered = question.lower()
    hits = 0
    for keyword in chapter.keywords:
        needle = keyword.strip().lower()
        if len(needle) >= 2 and keyword_in_question(needle, lowered):
            hits += 1
    title_words = [word for word in chapter.title.lower().split() if len(word) >= 4]
    for word in title_words:
        if word in lowered:
            hits += 1
    return hits


def choose_chapters(question: str, chapters: list[Chapter], *, max_chapters: int = 2) -> list[Chapter]:
    scored: list[tuple[int, Chapter]] = []
    for chapter in chapters:
        score = chapter_score(question, chapter)
        if score > 0:
            scored.append((score, chapter))
    scored.sort(key=lambda item: item[0], reverse=True)
    if not scored:
        return []
    best = scored[0][0]
    chosen: list[Chapter] = []
    for score, chapter in scored:
        if score != best:
            break
        chosen.append(chapter)
        if len(chosen) >= max_chapters:
            break
    return chosen
