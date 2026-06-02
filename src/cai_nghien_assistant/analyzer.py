"""Reusable local-AI analysis tasks.

The task is packaged as a scriptable pipeline step, not as an ad-hoc chat with
an agent. It caches each model call by source chunk + pipeline/model version.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import load_project_config
from .local_llm import LlamaCppClient
from .paths import configure_local_environment, to_project_relative
from .schema import KnowledgeChunk
from .storage import atomic_write_json, sha256_text, write_jsonl


def analysis_prompt(chunk: KnowledgeChunk) -> str:
    return f"""Phân tích đoạn transcript sau thành JSON thuần.

Luật:
- Chỉ trích xuất ý có bằng chứng trực tiếp trong đoạn.
- Không suy đoán, không thêm kiến thức trading.
- Tách "content_facts" và "style_observations".
- content_facts: mảng ý kiến thức, mỗi ý có "text" và "evidence_quote".
- style_observations: mảng quan sát về cách nói, không phải sự thật nội dung.
- Nếu không có gì rõ, trả mảng rỗng.

Metadata:
video_id={chunk.video_id}
title={chunk.title}
published_at={chunk.published_at}
start={chunk.start}
end={chunk.end}

Transcript:
{chunk.text}

JSON:
"""


def _safe_json_object(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return {"content_facts": [], "style_observations": [], "parse_error": text[:500]}
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {"content_facts": [], "style_observations": [], "parse_error": text[:500]}
    if not isinstance(data, dict):
        return {"content_facts": [], "style_observations": []}
    data.setdefault("content_facts", [])
    data.setdefault("style_observations", [])
    return data


def run_local_analysis(
    root: str | Path | None,
    chunks: list[KnowledgeChunk],
    endpoint: str,
    model_id: str = "llama.cpp-local",
    limit: int | None = None,
) -> dict[str, int]:
    """Run local model extraction and write separate content/style outputs."""

    root_path = Path(root or ".").resolve()
    configure_local_environment(root_path)
    config = load_project_config(root_path)
    client = LlamaCppClient(endpoint=endpoint)
    pipeline_version = config["pipeline"]["version"]
    cache_dir = root_path / config["storage"]["analysis_dir"] / "cache" / "llm"
    content_dir = root_path / config["storage"]["analysis_dir"] / "extractions" / "content"
    style_dir = root_path / config["storage"]["analysis_dir"] / "extractions" / "style"
    cache_dir.mkdir(parents=True, exist_ok=True)
    content_dir.mkdir(parents=True, exist_ok=True)
    style_dir.mkdir(parents=True, exist_ok=True)

    content_rows: list[dict[str, Any]] = []
    style_rows: list[dict[str, Any]] = []
    processed = 0

    for chunk in chunks[:limit]:
        cache_key = sha256_text("|".join([chunk.chunk_id, pipeline_version, model_id, endpoint]))
        cache_path = cache_dir / f"{cache_key}.json"
        if cache_path.exists():
            result = json.loads(cache_path.read_text(encoding="utf-8"))
        else:
            result = _safe_json_object(client.complete(analysis_prompt(chunk)))
            atomic_write_json(
                cache_path,
                {
                    "cache_key": cache_key,
                    "model_id": model_id,
                    "pipeline_version": pipeline_version,
                    "source_chunk_id": chunk.chunk_id,
                    "result": result,
                },
                root_path,
            )
            result = {"result": result}

        extracted = result.get("result", result)
        for item in extracted.get("content_facts", []) or []:
            if not isinstance(item, dict) or not item.get("text"):
                continue
            content_rows.append(
                {
                    "chunk_id": f"content-note:{chunk.chunk_id}:{sha256_text(item['text'])[:12]}",
                    "video_id": chunk.video_id,
                    "title": chunk.title,
                    "published_at": chunk.published_at,
                    "start": chunk.start,
                    "end": chunk.end,
                    "text": item["text"],
                    "evidence_quote": item.get("evidence_quote", ""),
                    "source_type": "local_llm_content_extraction",
                    "source_path": chunk.source_path,
                    "pipeline_version": pipeline_version,
                    "model_id": model_id,
                }
            )
        for item in extracted.get("style_observations", []) or []:
            text = item["text"] if isinstance(item, dict) and item.get("text") else str(item)
            if not text.strip():
                continue
            style_rows.append(
                {
                    "chunk_id": f"style:{chunk.video_id}:{sha256_text(text + chunk.chunk_id)[:16]}",
                    "video_id": chunk.video_id,
                    "title": chunk.title,
                    "published_at": chunk.published_at,
                    "start": chunk.start,
                    "end": chunk.end,
                    "text": text,
                    "source_type": "local_llm_style_extraction",
                    "source_path": chunk.source_path,
                    "pipeline_version": pipeline_version,
                    "model_id": model_id,
                }
            )
        processed += 1

    if content_rows:
        write_jsonl(content_dir / "content_notes.jsonl", content_rows, root_path)
    if style_rows:
        write_jsonl(style_dir / "style_notes.jsonl", style_rows, root_path)

    return {"processed_chunks": processed, "content_notes": len(content_rows), "style_notes": len(style_rows)}

