"""Batch extract structured knowledge facts per video."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from ..config import load_project_config
from ..knowledge import iter_segments_for_index
from ..paths import configure_local_environment, to_project_relative
from ..storage import atomic_write_json, write_jsonl
from ..youtube_collect import catalog_entries_filtered, load_latest_catalog
from .extractor import facts_from_ocr, facts_from_segments
from .schema import KnowledgeFact


def knowledge_root(root: Path) -> Path:
    config = load_project_config(root)
    ke = config.get("knowledge_extraction") or {}
    rel = str(ke.get("output_dir") or "data/analysis/knowledge")
    return root / rel


def video_dir(root: Path, video_id: str) -> Path:
    path = knowledge_root(root) / video_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def extraction_options(root: Path) -> dict[str, Any]:
    config = load_project_config(root)
    ke = config.get("knowledge_extraction") or {}
    return {
        "min_chars": int(ke.get("min_sentence_chars") or 20),
        "require_domain_term": bool(ke.get("require_domain_term", True)),
        "include_ocr": bool(ke.get("include_ocr", True)),
    }


def catalog_video_ids(root: Path, content_type: str | None, published_year: int | None = None) -> set[str]:
    entries = catalog_entries_filtered(root, content_type=content_type, published_year=published_year)
    return {entry["video_id"] for entry in entries if entry.get("video_id")}


def group_segments_by_video(root: Path, allowed_video_ids: set[str] | None) -> dict[str, list]:
    grouped: dict[str, list] = defaultdict(list)
    for segment in iter_segments_for_index(root):
        if allowed_video_ids is not None and segment.video_id not in allowed_video_ids:
            continue
        grouped[segment.video_id].append(segment)
    return grouped


def load_corpus_rows(root: Path) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rows: list[dict[str, Any]] = []
    by_category: dict[str, int] = defaultdict(int)
    base = knowledge_root(root)
    if not base.exists():
        return rows, {}
    for video_path in sorted(base.iterdir()):
        if not video_path.is_dir():
            continue
        facts_path = video_path / "facts.jsonl"
        if not facts_path.exists():
            continue
        for line in facts_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            rows.append(row)
            by_category[str(row.get("category") or "unknown")] += 1
    return rows, dict(by_category)


def write_video_facts(root: Path, video_id: str, facts: list[KnowledgeFact], *, force: bool) -> int:
    out_path = video_dir(root, video_id) / "facts.jsonl"
    if out_path.exists() and not force:
        return sum(1 for line in out_path.read_text(encoding="utf-8").splitlines() if line.strip())
    write_jsonl(out_path, [fact.to_dict() for fact in facts], root)
    return len(facts)


def run_extract_batch(
    root: str | Path | None = None,
    *,
    limit: int | None = None,
    content_type: str | None = None,
    published_year: int | None = None,
    force: bool = False,
) -> dict[str, Any]:
    root_path = Path(root or ".").resolve()
    configure_local_environment(root_path)
    config = load_project_config(root_path)
    pipeline_version = config["pipeline"]["version"]
    opts = extraction_options(root_path)

    allowed = catalog_video_ids(root_path, content_type, published_year) if content_type or published_year else None
    grouped = group_segments_by_video(root_path, allowed)
    video_ids = sorted(grouped.keys())
    if limit:
        video_ids = video_ids[:limit]

    transcript_facts = 0
    ocr_facts = 0

    ocr_by_video: dict[str, list[KnowledgeFact]] = defaultdict(list)
    if opts["include_ocr"]:
        for fact in facts_from_ocr(root_path):
            if allowed is not None and fact.video_id not in allowed:
                continue
            ocr_by_video[fact.video_id].append(fact)

    for video_id in video_ids:
        segments = grouped[video_id]
        transcript_fact_list = facts_from_segments(
            segments,
            root_path,
            min_chars=opts["min_chars"],
            require_domain_term=opts["require_domain_term"],
        )
        ocr_fact_list = ocr_by_video.get(video_id, [])
        transcript_facts += len(transcript_fact_list)
        ocr_facts += len(ocr_fact_list)
        write_video_facts(root_path, video_id, transcript_fact_list + ocr_fact_list, force=force)

    corpus_rows, by_category = load_corpus_rows(root_path)
    corpus_path = knowledge_root(root_path) / "corpus.jsonl"
    write_jsonl(corpus_path, corpus_rows, root_path)

    manifest = {
        "pipeline_version": pipeline_version,
        "videos_processed": len(video_ids),
        "transcript_facts": transcript_facts,
        "ocr_facts": ocr_facts,
        "total_facts": len(corpus_rows),
        "by_category": dict(sorted(by_category.items())),
        "corpus_path": to_project_relative(corpus_path, root_path),
    }
    atomic_write_json(knowledge_root(root_path) / "manifest.json", manifest, root_path)
    return manifest
