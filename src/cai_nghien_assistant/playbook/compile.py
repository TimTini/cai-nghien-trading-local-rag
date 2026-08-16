"""Compile a new video into the playbook without rewriting existing chapters."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..config import load_project_config
from ..local_llm import LlamaCppClient
from ..paths import configure_local_environment
from ..storage import atomic_write_json, atomic_write_text, sha256_text
from .assemble import assemble_video_sources
from .paths import playbook_dir, video_dir, videos_root
from .schema import PlaybookRule, VideoArticle

ARTICLE_PROMPT = """Bạn đọc toàn bộ lời một video trading. Viết JSON thuần, không markdown.

Luật:
- Giữ nguyên ý, đủ điều kiện và ngoại lệ. Không cắt thành câu rời.
- Tách rule bền (kind=doctrine) và nhận định theo ngày video (kind=time_bound).
- Mỗi rule có text (đủ luận), conditions, exceptions, start, end, evidence_quote.
- topics: vài từ khóa chủ đề (ví dụ risk, entry, mindset).
- Không bịa. Không có thì mảng rỗng.

Metadata:
video_id={video_id}
title={title}

Lời video:
{source}

JSON:
{{
  "thesis": "",
  "topics": [],
  "rules": [
    {{
      "text": "",
      "conditions": [],
      "exceptions": [],
      "start": 0,
      "end": 0,
      "evidence_quote": "",
      "kind": "doctrine"
    }}
  ]
}}
"""


def append_chapter_update(path: str | Path, root: str | Path | None, heading: str, body: str) -> None:
    target = Path(path)
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    if heading and heading in existing:
        return
    block = f"\n\n## {heading}\n\n{body.strip()}\n"
    atomic_write_text(target, existing.rstrip() + block + "\n", root)


def article_markdown(article: VideoArticle) -> str:
    lines = [
        f"# {article.title}",
        "",
        f"- video_id: {article.video_id}",
        f"- published_at: {article.published_at}",
        f"- source_type: {article.source_type}",
        f"- topics: {', '.join(article.topics)}",
        "",
        "## Luận chính",
        "",
        article.thesis,
        "",
        "## Nguyên tắc (đủ điều kiện / ngoại lệ)",
        "",
    ]
    for rule in article.rules:
        lines.append(f"### {rule.text}")
        lines.append("")
        if rule.conditions:
            lines.append("Điều kiện: " + "; ".join(rule.conditions))
        if rule.exceptions:
            lines.append("Ngoại lệ: " + "; ".join(rule.exceptions))
        if rule.evidence_quote:
            lines.append(f"Dẫn: {rule.evidence_quote}")
        lines.append(f"Loại: {rule.kind}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _parse_article_json(raw: str, *, video_id: str, title: str, published_at: str, source_type: str) -> VideoArticle | None:
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        data = json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    rules: list[PlaybookRule] = []
    for item in data.get("rules") or []:
        if not isinstance(item, dict) or not item.get("text"):
            continue
        quote = str(item.get("evidence_quote") or item["text"])
        rule_id = sha256_text(f"{video_id}|{item.get('start')}|{item['text']}")[:16]
        rules.append(
            PlaybookRule(
                rule_id=rule_id,
                text=str(item["text"]),
                conditions=[str(part) for part in (item.get("conditions") or [])],
                exceptions=[str(part) for part in (item.get("exceptions") or [])],
                start=item.get("start"),
                end=item.get("end"),
                evidence_quote=quote,
                kind=str(item.get("kind") or "doctrine"),
            )
        )
    return VideoArticle(
        video_id=video_id,
        title=title,
        published_at=published_at,
        source_type=source_type,
        thesis=str(data.get("thesis") or ""),
        rules=rules,
        topics=[str(item) for item in (data.get("topics") or [])],
    )


def _read_source_header(source_text: str) -> dict[str, str]:
    header = {"title": "", "published_at": "", "source_type": "", "video_id": ""}
    for line in source_text.splitlines()[:12]:
        if line.startswith("# "):
            header["title"] = line[2:].strip()
        elif line.startswith("- video_id:"):
            header["video_id"] = line.split(":", 1)[1].strip()
        elif line.startswith("- published_at:"):
            header["published_at"] = line.split(":", 1)[1].strip()
        elif line.startswith("- source_type:"):
            header["source_type"] = line.split(":", 1)[1].strip()
    return header


def write_article_files(root: Path, article: VideoArticle) -> None:
    out_dir = video_dir(root, article.video_id)
    atomic_write_json(out_dir / "article.json", article.to_dict(), root)
    atomic_write_text(out_dir / "article.md", article_markdown(article), root)


def compile_article_from_source(
    root: Path,
    video_id: str,
    *,
    endpoint: str,
) -> VideoArticle | None:
    source_path = video_dir(root, video_id) / "source.md"
    if not source_path.exists():
        return None
    source_text = source_path.read_text(encoding="utf-8")
    header = _read_source_header(source_text)
    client = LlamaCppClient(endpoint=endpoint, timeout=300)
    prompt = ARTICLE_PROMPT.format(
        video_id=video_id,
        title=header.get("title") or video_id,
        source=source_text,
    )
    raw = client.complete(prompt, max_tokens=1800, temperature=0.1)
    article = _parse_article_json(
        raw,
        video_id=video_id,
        title=header.get("title") or video_id,
        published_at=header.get("published_at") or "",
        source_type=header.get("source_type") or "",
    )
    if article is None:
        return None
    write_article_files(root, article)
    return article


def _append_article_to_chapters(root: Path, article: VideoArticle) -> int:
    index_file = playbook_dir(root) / "index.json"
    if not index_file.exists():
        return 0
    data = json.loads(index_file.read_text(encoding="utf-8"))
    chapters = data.get("chapters") or []
    topic_set = {item.lower() for item in article.topics}
    doctrine_lines = [rule.text for rule in article.rules if rule.kind != "time_bound"]
    if not doctrine_lines:
        return 0
    body = "\n".join(f"- {line}" for line in doctrine_lines)
    heading = f"Cập nhật từ video {article.video_id} ({article.published_at})"
    updated = 0
    for row in chapters:
        topic_id = str(row.get("topic_id") or "")
        keywords = [str(item).lower() for item in (row.get("keywords") or [])]
        matched = topic_id in topic_set or any(word in topic_set for word in keywords)
        if not matched and article.topics:
            matched = any(topic in " ".join(keywords) for topic in topic_set)
        if not matched:
            continue
        file_name = str(row.get("file") or "")
        if not file_name:
            continue
        append_chapter_update(
            playbook_dir(root) / file_name,
            root,
            heading=heading,
            body=body,
        )
        updated += 1
    return updated


def run_compile_playbook(
    root: str | Path | None = None,
    *,
    limit: int | None = None,
    force: bool = False,
    endpoint: str | None = None,
) -> dict[str, Any]:
    root_path = Path(root or ".").resolve()
    configure_local_environment(root_path)
    assemble = assemble_video_sources(root_path, limit=limit, force=force)
    videos_path = videos_root(root_path)
    if videos_path.exists():
        video_ids = sorted(path.name for path in videos_path.iterdir() if path.is_dir())
    else:
        video_ids = []
    if limit:
        video_ids = video_ids[:limit]

    articles_written = 0
    needs_article = 0
    chapter_updates = 0
    for video_id in video_ids:
        article_path = video_dir(root_path, video_id) / "article.json"
        if article_path.exists() and not force:
            article = VideoArticle.from_dict(json.loads(article_path.read_text(encoding="utf-8")))
            chapter_updates += _append_article_to_chapters(root_path, article)
            continue
        if endpoint:
            article = compile_article_from_source(root_path, video_id, endpoint=endpoint)
            if article is None:
                needs_article += 1
                continue
            articles_written += 1
            chapter_updates += _append_article_to_chapters(root_path, article)
            continue
        needs_article += 1

    result = {
        "assemble": assemble,
        "articles_written": articles_written,
        "needs_article": needs_article,
        "chapter_updates": chapter_updates,
        "allow_cloud": bool(load_project_config(root_path).get("guardrails", {}).get("allow_cloud")),
    }
    atomic_write_json(playbook_dir(root_path) / "compile_manifest.json", result, root_path)
    return result
