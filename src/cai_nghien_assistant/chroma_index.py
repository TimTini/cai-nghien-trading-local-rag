"""Optional project-local Chroma index.

Chroma is not the default MVP backend because it is an optional dependency.
When enabled, the persistent DB path is still under data/analysis/index/chroma.
The fallback hash embedding below avoids surprise model downloads; replace it
with BGE-M3 only after placing/caching the embedding model inside the project.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Iterable

from .config import config_path
from .paths import configure_local_environment
from .schema import KnowledgeChunk


class HashEmbeddingFunction:
    """Deterministic local embedding fallback with no network/model cache."""

    def __init__(self, dimensions: int = 384):
        self.dimensions = dimensions

    def __call__(self, input: list[str]) -> list[list[float]]:  # Chroma embedding function protocol
        return [self._embed(text) for text in input]

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = text.lower().split()
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


def _import_chroma():
    try:
        import chromadb  # type: ignore
    except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("Missing Chroma. Install with: python -m pip install -e .[ml]") from exc
    return chromadb


def build_chroma_index(root: str | Path | None, chunks: Iterable[KnowledgeChunk]) -> int:
    """Upsert content/style chunks into a persistent Chroma collection."""

    root_path = Path(root or ".").resolve()
    configure_local_environment(root_path)
    chromadb = _import_chroma()
    chroma_path = config_path(root_path, "retrieval.chroma_path")
    client = chromadb.PersistentClient(path=str(chroma_path))
    collection = client.get_or_create_collection(
        name="channel_knowledge",
        embedding_function=HashEmbeddingFunction(),
        metadata={"description": "Project-local Cai Nghien Trading evidence chunks"},
    )

    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict[str, object]] = []
    for chunk in chunks:
        ids.append(chunk.chunk_id)
        documents.append(chunk.text)
        metadatas.append(
            {
                "kind": chunk.kind,
                "video_id": chunk.video_id,
                "title": chunk.title,
                "published_at": chunk.published_at,
                "start": chunk.start if chunk.start is not None else -1,
                "end": chunk.end if chunk.end is not None else -1,
                "source_type": chunk.source_type,
                "source_path": chunk.source_path,
                "pipeline_version": chunk.pipeline_version,
            }
        )
    if not ids:
        return 0
    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
    return len(ids)

