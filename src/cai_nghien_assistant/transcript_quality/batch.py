"""Batch làm sạch transcript: cũ → mới, resume, idempotent."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..config import load_project_config
from ..paths import configure_local_environment
from ..storage import atomic_write_json
from ..youtube_collect import catalog_entries_filtered
from .cleaner import clean_all_segments, write_ai_cleaned
from .raw_layer import ensure_raw_layer, ordered_video_ids_with_transcripts, quality_dir
from .review_store import (
    default_review_state,
    init_approved_from_ai,
    load_review_state,
    save_review_state,
    should_skip_ai_clean,
)
from .schema import CLEANER_LOGIC_VERSION


def batch_state_path(root: Path) -> Path:
    config = load_project_config(root)
    return root / config["storage"]["analysis_dir"] / "state" / "transcript_clean_batch.json"


def load_batch_state(root: Path) -> dict[str, Any]:
    path = batch_state_path(root)
    if not path.exists():
        return {"processed": {}, "last_video_id": None, "paused": False}
    return json.loads(path.read_text(encoding="utf-8"))


def save_batch_state(root: Path, state: dict[str, Any]) -> None:
    atomic_write_json(batch_state_path(root), state, root)


def load_glossary_terms(root: Path) -> list[str]:
    config = load_project_config(root)
    glossary_path = root / config["storage"]["analysis_dir"] / "transcript_quality" / "glossary.json"
    if not glossary_path.exists():
        return []
    data = json.loads(glossary_path.read_text(encoding="utf-8"))
    return list(data.get("terms") or [])


def append_glossary_from_approved(root: Path, video_id: str) -> None:
    """Thu thập từ đã approved — chỉ tham chiếu ngữ cảnh, không bịa."""

    config = load_project_config(root)
    approved_path = quality_dir(root, video_id) / "approved.jsonl"
    if not approved_path.exists():
        return
    glossary_path = root / config["storage"]["analysis_dir"] / "transcript_quality" / "glossary.json"
    existing: set[str] = set()
    if glossary_path.exists():
        existing = set(json.loads(glossary_path.read_text(encoding="utf-8")).get("terms") or [])
    for line in approved_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        text = str(row.get("text") or "").lower()
        for hint in ("stop loss", "take profit", "đòn bẩy", "funding", "liquidation", "rsi", "macd"):
            if hint in text:
                existing.add(hint)
    atomic_write_json(glossary_path, {"terms": sorted(existing)}, root)


def resolve_engine(model_id: str, engine: str | None) -> str:
    if engine:
        return engine.strip().lower()
    mid = (model_id or "conservative-refine").strip().lower()
    if mid in ("rule-only", "rules"):
        return "rule-only"
    if mid in ("asr-reprocess", "asr_reprocess"):
        return "asr-reprocess"
    if mid.startswith("llama:") or mid == "llm":
        return "llm"
    return "conservative-refine"


def clean_one_video(
    root: Path,
    video_id: str,
    *,
    model_id: str = "conservative-refine",
    engine: str | None = None,
    endpoint: str | None = None,
    force: bool = False,
) -> dict[str, Any]:
    segments, raw_hash, raw_source_path = ensure_raw_layer(root, video_id)
    if not segments:
        return {"video_id": video_id, "status": "skipped", "reason": "no_raw_segments"}

    state = load_review_state(root, video_id)
    if state and state.status == "approved" and not force:
        return {"video_id": video_id, "status": "skipped", "reason": "already_approved"}

    resolved_engine = resolve_engine(model_id, engine)
    effective_model_id = model_id if not endpoint else f"llama:{model_id}"
    if endpoint:
        resolved_engine = "llm"

    if should_skip_ai_clean(root, video_id, raw_hash, effective_model_id, force=force):
        return {"video_id": video_id, "status": "skipped", "reason": "ai_clean_unchanged"}

    glossary = load_glossary_terms(root)
    cleaned, changes = clean_all_segments(
        segments,
        root=root,
        engine=resolved_engine,
        endpoint=endpoint,
        glossary_terms=glossary,
    )
    write_ai_cleaned(
        root,
        video_id,
        cleaned,
        changes,
        raw_source_hash=raw_hash,
        raw_source_path=raw_source_path,
        model_id=effective_model_id,
    )
    init_approved_from_ai(root, video_id)

    suspicious = sum(1 for c in changes if c.confidence == "low" or c.needs_relisten)
    new_state = default_review_state(
        video_id,
        title=segments[0].title,
        published_at=segments[0].published_at,
        raw_source_hash=raw_hash,
        raw_source_path=raw_source_path,
    )
    new_state.ai_input_hash = raw_hash
    new_state.cleaner_logic_version = CLEANER_LOGIC_VERSION
    new_state.model_id = effective_model_id
    new_state.suspicious_count = suspicious
    new_state.status = "has_suspicious" if suspicious else "ai_done_unreviewed"
    save_review_state(root, new_state)

    return {
        "video_id": video_id,
        "status": "cleaned",
        "segments": len(cleaned),
        "changes": len(changes),
        "suspicious": suspicious,
    }


def run_clean_batch(
    root: str | Path | None = None,
    *,
    limit: int | None = None,
    content_type: str | None = None,
    offset: int = 0,
    published_year: int | None = None,
    model_id: str = "conservative-refine",
    engine: str | None = None,
    endpoint: str | None = None,
    force: bool = False,
    pause_file: str | None = None,
) -> dict[str, Any]:
    root_path = Path(root or ".").resolve()
    configure_local_environment(root_path)
    pause_path = Path(pause_file) if pause_file else root_path / "data" / "analysis" / "state" / "transcript_clean.pause"

    ctype_filter = None if content_type in {None, "", "regular+livestream", "all"} else content_type
    video_ids = ordered_video_ids_with_transcripts(root_path, ctype_filter)
    if published_year is not None or content_type:
        allowed = {
            row["video_id"]
            for row in catalog_entries_filtered(root_path, content_type=content_type, published_year=published_year)
            if row.get("video_id")
        }
        video_ids = [vid for vid in video_ids if vid in allowed]
    if offset:
        video_ids = video_ids[offset:]
    if limit:
        video_ids = video_ids[:limit]

    batch_state = load_batch_state(root_path)
    summary: dict[str, Any] = {"processed": [], "skipped": [], "errors": []}

    for video_id in video_ids:
        if pause_path.exists():
            batch_state["paused"] = True
            save_batch_state(root_path, batch_state)
            summary["paused_at"] = video_id
            break
        try:
            result = clean_one_video(
                root_path,
                video_id,
                model_id=model_id,
                engine=engine,
                endpoint=endpoint,
                force=force,
            )
            batch_state["processed"][video_id] = result
            batch_state["last_video_id"] = video_id
            key = "processed" if result.get("status") == "cleaned" else "skipped"
            summary[key].append(result)
        except Exception as exc:  # pragma: no cover - batch continues
            batch_state["processed"][video_id] = {"status": "error", "error": str(exc)}
            summary["errors"].append({"video_id": video_id, "error": str(exc)})
        save_batch_state(root_path, batch_state)

    batch_state["paused"] = pause_path.exists()
    save_batch_state(root_path, batch_state)
    summary["total_videos"] = len(video_ids)
    return summary
