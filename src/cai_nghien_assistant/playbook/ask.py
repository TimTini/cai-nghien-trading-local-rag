"""Answer by returning whole matching playbook chapters."""

from __future__ import annotations

import json
from pathlib import Path

from ..config import load_project_config
from ..paths import configure_local_environment
from .paths import index_path, playbook_dir
from .router import choose_chapters
from .schema import Chapter

UNKNOWN_FALLBACK = "Tôi không biết dựa trên dữ liệu đã phân tích từ kênh này."


def load_chapters(root: Path) -> list[Chapter]:
    catalog_path = index_path(root)
    if not catalog_path.exists():
        return []
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    rows = data.get("chapters") or []
    chapters: list[Chapter] = []
    base = playbook_dir(root)
    for row in rows:
        file_name = str(row.get("file") or "")
        body_path = base / file_name
        body = body_path.read_text(encoding="utf-8") if body_path.exists() else ""
        chapters.append(
            Chapter(
                topic_id=str(row.get("topic_id") or ""),
                title=str(row.get("title") or ""),
                keywords=[str(item) for item in (row.get("keywords") or [])],
                path=file_name,
                body=body,
            )
        )
    return chapters


def ask_playbook(root: str | Path | None, question: str) -> str:
    root_path = Path(root or ".").resolve()
    configure_local_environment(root_path)
    config = load_project_config(root_path)
    unknown = str(config.get("guardrails", {}).get("unknown_answer") or UNKNOWN_FALLBACK)
    chapters = load_chapters(root_path)
    chosen = choose_chapters(question, chapters)
    if not chosen:
        return unknown
    parts: list[str] = []
    for chapter in chosen:
        body = chapter.body.strip()
        if body:
            parts.append(body)
    if not parts:
        return unknown
    return "\n\n".join(parts)
