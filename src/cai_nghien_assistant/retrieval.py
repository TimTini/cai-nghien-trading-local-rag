"""Project-local SQLite retrieval index."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Iterable

from .config import config_path
from .paths import configure_local_environment
from .schema import Evidence, KnowledgeChunk


TERM_RE = re.compile(r"[\wÀ-ỹ]+", re.UNICODE)


def query_terms(query: str) -> list[str]:
    return [term for term in TERM_RE.findall(query.lower()) if len(term) >= 2]


def format_timestamp(value: float | None) -> str:
    if value is None:
        return ""
    total = max(0, int(value))
    hours = total // 3600
    minutes = (total % 3600) // 60
    seconds = total % 60
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


class SearchIndex:
    """Small retriever that keeps content and style in the same DB but separated by kind."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.fts_enabled = False
        self.init_schema()

    @classmethod
    def from_project(cls, root: str | Path | None = None) -> "SearchIndex":
        root_path = Path(root or ".").resolve()
        configure_local_environment(root_path)
        return cls(config_path(root_path, "retrieval.index_path"))

    def close(self) -> None:
        self.connection.close()

    def init_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                video_id TEXT NOT NULL,
                title TEXT NOT NULL,
                published_at TEXT NOT NULL,
                start REAL,
                end REAL,
                text TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_path TEXT NOT NULL,
                pipeline_version TEXT NOT NULL
            );
            """
        )
        try:
            self.connection.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(chunk_id UNINDEXED, title, text, tokenize='unicode61')"
            )
            self.fts_enabled = True
        except sqlite3.OperationalError:
            self.fts_enabled = False
        self.connection.commit()

    def count_chunks(self) -> int:
        row = self.connection.execute("SELECT COUNT(*) AS count FROM chunks").fetchone()
        return int(row["count"])

    def clear(self) -> None:
        self.connection.execute("DELETE FROM chunks")
        if self.fts_enabled:
            self.connection.execute("DELETE FROM chunks_fts")
        self.connection.commit()

    def upsert_chunks(self, chunks: Iterable[KnowledgeChunk]) -> int:
        changed = 0
        for chunk in chunks:
            result = self.connection.execute(
                """
                INSERT OR IGNORE INTO chunks (
                    chunk_id, kind, video_id, title, published_at, start, end,
                    text, source_type, source_path, pipeline_version
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk.chunk_id,
                    chunk.kind,
                    chunk.video_id,
                    chunk.title,
                    chunk.published_at,
                    chunk.start,
                    chunk.end,
                    chunk.text,
                    chunk.source_type,
                    chunk.source_path,
                    chunk.pipeline_version,
                ),
            )
            if result.rowcount:
                changed += 1
            if self.fts_enabled:
                self.connection.execute("DELETE FROM chunks_fts WHERE chunk_id = ?", (chunk.chunk_id,))
                self.connection.execute(
                    "INSERT OR REPLACE INTO chunks_fts (chunk_id, title, text) VALUES (?, ?, ?)",
                    (chunk.chunk_id, chunk.title, chunk.text),
                )
        self.connection.commit()
        return changed

    def replace_chunks(self, chunks: Iterable[KnowledgeChunk]) -> int:
        self.clear()
        return self.upsert_chunks(chunks)

    def _search_fts(self, query: str, kind: str, limit: int) -> list[Evidence]:
        terms = query_terms(query)
        if not terms:
            return []
        match_query = " OR ".join(f'"{term}"' for term in terms[:12])
        rows = self.connection.execute(
            """
            SELECT c.*, bm25(chunks_fts) AS score
            FROM chunks_fts
            JOIN chunks c ON c.chunk_id = chunks_fts.chunk_id
            WHERE chunks_fts MATCH ? AND c.kind = ?
            ORDER BY score ASC, c.published_at DESC, c.start ASC
            LIMIT ?
            """,
            (match_query, kind, limit),
        ).fetchall()
        return [self._row_to_evidence(row) for row in rows]

    def _search_like(self, query: str, kind: str, limit: int) -> list[Evidence]:
        terms = query_terms(query)
        if not terms:
            return []
        rows = self.connection.execute(
            "SELECT * FROM chunks WHERE kind = ? ORDER BY published_at DESC, start ASC",
            (kind,),
        ).fetchall()
        scored: list[Evidence] = []
        for row in rows:
            haystack = f"{row['title']} {row['text']}".lower()
            hits = sum(1 for term in terms if term in haystack)
            if hits:
                evidence = self._row_to_evidence(row, score=-float(hits))
                scored.append(evidence)
        scored.sort(key=lambda item: item.published_at, reverse=True)
        scored.sort(key=lambda item: item.score)
        return scored[:limit]

    def search(self, query: str, kind: str = "content", limit: int = 5) -> list[Evidence]:
        if kind not in {"content", "style"}:
            raise ValueError("kind must be 'content' or 'style'")
        if self.fts_enabled:
            try:
                return self._search_fts(query, kind, limit)
            except sqlite3.OperationalError:
                return self._search_like(query, kind, limit)
        return self._search_like(query, kind, limit)

    @staticmethod
    def _row_to_evidence(row: sqlite3.Row, score: float | None = None) -> Evidence:
        return Evidence(
            chunk_id=row["chunk_id"],
            kind=row["kind"],
            video_id=row["video_id"],
            title=row["title"],
            published_at=row["published_at"],
            start=row["start"],
            end=row["end"],
            text=row["text"],
            source_type=row["source_type"],
            source_path=row["source_path"],
            score=float(row["score"] if score is None and "score" in row.keys() else score or 0.0),
        )


def build_index(root: str | Path | None, chunks: Iterable[KnowledgeChunk]) -> int:
    index = SearchIndex.from_project(root)
    try:
        return index.upsert_chunks(chunks)
    finally:
        index.close()
