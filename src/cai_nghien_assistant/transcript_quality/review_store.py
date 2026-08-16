"""Trạng thái review, approved, lịch sử rollback."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..storage import atomic_write_json, read_jsonl, write_jsonl
from .raw_layer import quality_dir
from .schema import CLEANER_LOGIC_VERSION, ReviewState


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def review_state_path(root: Path, video_id: str) -> Path:
    return quality_dir(root, video_id) / "review_state.json"


def load_review_state(root: Path, video_id: str) -> ReviewState | None:
    path = review_state_path(root, video_id)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return ReviewState(**data)


def save_review_state(root: Path, state: ReviewState) -> None:
    atomic_write_json(review_state_path(root, state.video_id), state.to_dict(), root)


def default_review_state(
    video_id: str,
    *,
    title: str = "",
    published_at: str = "",
    raw_source_hash: str = "",
    raw_source_path: str = "",
) -> ReviewState:
    return ReviewState(
        video_id=video_id,
        status="pending_ai",
        title=title,
        published_at=published_at,
        raw_source_hash=raw_source_hash,
        raw_source_path=raw_source_path,
    )


def load_ai_meta(root: Path, video_id: str) -> dict[str, Any]:
    path = quality_dir(root, video_id) / "ai_cleaned.meta.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def should_skip_ai_clean(
    root: Path,
    video_id: str,
    raw_source_hash: str,
    model_id: str,
    force: bool = False,
) -> bool:
    """Bỏ qua nếu đã có AI cùng input + logic + model và không force."""

    if force:
        return False
    meta = load_ai_meta(root, video_id)
    if not meta:
        return False
    state = load_review_state(root, video_id)
    if state and state.status == "approved":
        return True
    return (
        meta.get("input_raw_hash") == raw_source_hash
        and meta.get("cleaner_logic_version") == CLEANER_LOGIC_VERSION
        and str(meta.get("model_id")) == model_id
        and (quality_dir(root, video_id) / "ai_cleaned.jsonl").exists()
    )


def init_approved_from_ai(root: Path, video_id: str) -> int:
    """Tạo approved.jsonl từ ai_cleaned nếu chưa có (chưa review)."""

    out_dir = quality_dir(root, video_id)
    approved_path = out_dir / "approved.jsonl"
    if approved_path.exists():
        return len(read_jsonl(approved_path))
    ai_path = out_dir / "ai_cleaned.jsonl"
    if not ai_path.exists():
        return 0
    rows = read_jsonl(ai_path)
    write_jsonl(approved_path, rows, root)
    return len(rows)


def _segment_text_by_id(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    return {str(row.get("segment_id") or ""): str(row.get("text") or "") for row in read_jsonl(path)}


def _load_raw_and_ai_maps(root: Path, video_id: str) -> tuple[dict[str, str], dict[str, str]]:
    """segment_id → text từ raw snapshot và ai_cleaned."""

    out_dir = quality_dir(root, video_id)
    raw_map: dict[str, str] = {}
    meta_path = out_dir / "raw.meta.json"
    if meta_path.exists():
        raw_file = json.loads(meta_path.read_text(encoding="utf-8")).get("raw_file") or "raw.jsonl"
        raw_map = _segment_text_by_id(out_dir / raw_file)
    ai_map = _segment_text_by_id(out_dir / "ai_cleaned.jsonl")
    return raw_map, ai_map


def _resolve_ai_text(
    segment_id: str,
    *,
    payload: dict[str, Any],
    changes: list[dict[str, Any]],
    ai_map: dict[str, str],
) -> str:
    from_payload = str(payload.get("ai_text") or "").strip()
    if from_payload:
        return from_payload
    for change in changes:
        if change.get("segment_id") == segment_id:
            text = str(change.get("ai_text") or "").strip()
            if text:
                return text
    return ai_map.get(segment_id, "").strip()


def _resolve_raw_text(
    segment_id: str,
    *,
    payload: dict[str, Any],
    changes: list[dict[str, Any]],
    raw_map: dict[str, str],
) -> str:
    from_payload = str(payload.get("raw_text") or "").strip()
    if from_payload:
        return from_payload
    for change in changes:
        if change.get("segment_id") == segment_id:
            text = str(change.get("raw_text") or "").strip()
            if text:
                return text
    return raw_map.get(segment_id, "").strip()


def snapshot_history(root: Path, video_id: str, label: str) -> None:
    """Lưu bản approved hiện tại để rollback."""

    out_dir = quality_dir(root, video_id)
    approved_path = out_dir / "approved.jsonl"
    if not approved_path.exists():
        return
    history_dir = out_dir / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    stamp = _now_iso().replace(":", "").replace("+00:00", "Z")
    target = history_dir / f"approved_{label}_{stamp}.jsonl"
    target.write_text(approved_path.read_text(encoding="utf-8"), encoding="utf-8")


def apply_review_action(
    root: Path,
    video_id: str,
    action: str,
    payload: dict[str, Any],
) -> ReviewState:
    """Các hành động từ UI: accept_low, accept_change, reject_change, edit_segment, approve, rollback."""

    state = load_review_state(root, video_id)
    if state is None:
        state = default_review_state(video_id)
    out_dir = quality_dir(root, video_id)
    approved_path = out_dir / "approved.jsonl"
    if not approved_path.exists():
        init_approved_from_ai(root, video_id)

    rows = read_jsonl(approved_path)
    by_id = {row["segment_id"]: row for row in rows}
    changes = read_jsonl(out_dir / "change_log.jsonl")
    raw_map, ai_map = _load_raw_and_ai_maps(root, video_id)

    if action == "accept_all_low_risk":
        changed_ids: list[str] = []
        for change in changes:
            if change.get("confidence") != "high" or change.get("needs_relisten"):
                continue
            segment_id = str(change.get("segment_id") or "")
            ai_text = str(change.get("ai_text") or "").strip() or ai_map.get(segment_id, "")
            if segment_id in by_id and ai_text:
                by_id[segment_id]["text"] = ai_text
                changed_ids.append(segment_id)
        for segment_id, ai_text in ai_map.items():
            if segment_id not in by_id or not ai_text:
                continue
            if by_id[segment_id].get("text") == ai_text:
                continue
            if any(
                c.get("segment_id") == segment_id
                and (c.get("needs_relisten") or c.get("confidence") == "low")
                for c in changes
            ):
                continue
            by_id[segment_id]["text"] = ai_text
            changed_ids.append(segment_id)
        state.partial_accepted_segment_ids.extend(changed_ids)
        state.accepted_low_risk = True
        state.status = "in_review"

    elif action == "accept_change":
        segment_id = str(payload.get("segment_id") or "")
        ai_text = _resolve_ai_text(segment_id, payload=payload, changes=changes, ai_map=ai_map)
        if segment_id in by_id and ai_text:
            by_id[segment_id]["text"] = ai_text
            if segment_id not in state.partial_accepted_segment_ids:
                state.partial_accepted_segment_ids.append(segment_id)
        state.status = "in_review"

    elif action == "reject_change":
        segment_id = str(payload.get("segment_id") or "")
        raw_text = _resolve_raw_text(segment_id, payload=payload, changes=changes, raw_map=raw_map)
        if segment_id in by_id and raw_text:
            by_id[segment_id]["text"] = raw_text
        if segment_id not in state.rejected_change_ids:
            state.rejected_change_ids.append(segment_id)
        state.status = "in_review"

    elif action == "edit_segment":
        segment_id = str(payload.get("segment_id") or "")
        new_text = str(payload.get("text") or "")
        if segment_id in by_id:
            snapshot_history(root, video_id, "before_manual_edit")
            by_id[segment_id]["text"] = new_text
            by_id[segment_id]["human_edited"] = True
        state.status = "in_review"

    elif action == "mark_needs_relisten":
        segment_id = str(payload.get("segment_id") or "")
        if segment_id in by_id:
            by_id[segment_id]["needs_relisten"] = True
        state.status = "has_suspicious"

    elif action == "approve":
        from .batch import append_glossary_from_approved

        state.status = "approved"
        state.approved_at = _now_iso()
        append_glossary_from_approved(root, video_id)

    elif action == "rollback":
        history_name = str(payload.get("history_file") or "")
        history_path = out_dir / "history" / history_name
        if history_path.exists():
            approved_path.write_text(history_path.read_text(encoding="utf-8"), encoding="utf-8")
            rows = read_jsonl(approved_path)
            by_id = {row["segment_id"]: row for row in rows}
        state.status = "in_review"

    ordered_rows = [by_id[row["segment_id"]] for row in rows if row["segment_id"] in by_id]
    write_jsonl(approved_path, ordered_rows, root)
    suspicious = sum(1 for row in by_id.values() if row.get("needs_relisten"))
    state.suspicious_count = suspicious
    if state.status != "approved" and suspicious > 0:
        state.status = "has_suspicious"
    save_review_state(root, state)
    return state


def list_history_files(root: Path, video_id: str) -> list[str]:
    history_dir = quality_dir(root, video_id) / "history"
    if not history_dir.exists():
        return []
    return sorted((path.name for path in history_dir.glob("approved_*.jsonl")), reverse=True)


def reset_video_for_reprocess(root: Path, video_id: str) -> dict[str, Any]:
    """Backup approved/AI outputs and reset review so mechanical reprocess can run again."""

    out_dir = quality_dir(root, video_id)
    removed: list[str] = []
    snapshot_history(root, video_id, "reprocess")
    for name in ("approved.jsonl", "ai_cleaned.jsonl", "ai_cleaned.meta.json"):
        path = out_dir / name
        if path.exists():
            path.unlink()
            removed.append(name)

    state = load_review_state(root, video_id)
    title = state.title if state else ""
    published_at = state.published_at if state else ""
    raw_hash = state.raw_source_hash if state else ""
    raw_path = state.raw_source_path if state else ""
    save_review_state(
        root,
        default_review_state(
            video_id,
            title=title,
            published_at=published_at,
            raw_source_hash=raw_hash,
            raw_source_path=raw_path,
        ),
    )
    return {"video_id": video_id, "removed": removed, "status": "reset"}


def reset_videos_for_reprocess(root: Path, video_ids: list[str]) -> list[dict[str, Any]]:
    return [reset_video_for_reprocess(root, video_id) for video_id in video_ids]
