from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from cai_nghien_assistant.chat import UNKNOWN_ANSWER, answer_question
from cai_nghien_assistant.paths import NON_PATH_ENV_KEYS, configure_local_environment
from cai_nghien_assistant.retrieval import SearchIndex
from cai_nghien_assistant.schema import KnowledgeChunk
from cai_nghien_assistant.storage import RawDataExistsError, write_json_once


class GuardrailTests(unittest.TestCase):
    def make_root(self) -> Path:
        root = Path(tempfile.mkdtemp())
        (root / "config").mkdir()
        (root / "config" / "project.toml").write_text(
            """
[retrieval]
index_path = "data/analysis/index/search.sqlite"
default_limit = 5
min_content_evidence = 1

[guardrails]
unknown_answer = "Tôi không biết dựa trên dữ liệu đã phân tích từ kênh này."
allow_cloud = false
allow_style_as_fact = false
""",
            encoding="utf-8",
        )
        (root / "pyproject.toml").write_text("[project]\nname='tmp'\nversion='0'\n", encoding="utf-8")
        return root

    def chunk(
        self,
        *,
        chunk_id: str,
        kind: str = "content",
        text: str = "quản trị rủi ro",
        published_at: str = "2024-01-01",
    ) -> KnowledgeChunk:
        return KnowledgeChunk(
            chunk_id=chunk_id,
            kind=kind,
            video_id="v1",
            title="Video test",
            published_at=published_at,
            start=12.0,
            end=30.0,
            text=text,
            source_type="youtube_subtitle",
            source_path="data/analysis/transcripts/v1/youtube.jsonl",
            pipeline_version="test",
        )

    def test_raw_write_once_refuses_mutation(self) -> None:
        root = self.make_root()
        target = root / "data" / "raw" / "videos" / "v1" / "metadata.json"
        write_json_once(target, {"title": "A"}, root)
        write_json_once(target, {"title": "A"}, root)
        with self.assertRaises(RawDataExistsError):
            write_json_once(target, {"title": "B"}, root)

    def test_env_paths_stay_inside_project(self) -> None:
        root = self.make_root()
        env = configure_local_environment(root)
        for key, value in env.items():
            if key in NON_PATH_ENV_KEYS:
                self.assertTrue(value)
                continue
            path = Path(value).resolve()
            self.assertTrue(path == root or root in path.parents, value)

    def test_index_upsert_is_idempotent(self) -> None:
        root = self.make_root()
        index = SearchIndex.from_project(root)
        try:
            chunk = self.chunk(chunk_id="content:v1:a")
            self.assertEqual(index.upsert_chunks([chunk, chunk]), 1)
            self.assertEqual(index.count_chunks(), 1)
        finally:
            index.close()

    def test_chat_refuses_without_content_evidence(self) -> None:
        root = self.make_root()
        index = SearchIndex.from_project(root)
        index.close()
        self.assertEqual(answer_question(root, "không có dữ liệu"), UNKNOWN_ANSWER)

    def test_style_evidence_is_not_fact_evidence(self) -> None:
        root = self.make_root()
        index = SearchIndex.from_project(root)
        try:
            index.upsert_chunks([self.chunk(chunk_id="style:v1:a", kind="style", text="hay nói anh em")])
        finally:
            index.close()
        self.assertEqual(answer_question(root, "anh em"), UNKNOWN_ANSWER)

    def test_newer_content_wins_when_score_ties(self) -> None:
        root = self.make_root()
        index = SearchIndex.from_project(root)
        try:
            old = self.chunk(chunk_id="content:v1:old", text="kỷ luật quản trị rủi ro", published_at="2021-01-01")
            new = self.chunk(chunk_id="content:v1:new", text="kỷ luật quản trị rủi ro", published_at="2025-01-01")
            index.upsert_chunks([old, new])
            evidence = index.search("quản trị rủi ro", kind="content", limit=2)
            self.assertGreaterEqual(len(evidence), 2)
            self.assertEqual(evidence[0].published_at, "2025-01-01")
        finally:
            index.close()


if __name__ == "__main__":
    unittest.main()
