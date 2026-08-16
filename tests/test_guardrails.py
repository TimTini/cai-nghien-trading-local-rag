from __future__ import annotations

import os
import importlib.util
import json
import types
import tempfile
import unittest
from pathlib import Path

from cai_nghien_assistant.chat import UNKNOWN_ANSWER, answer_question
from cai_nghien_assistant.media import _fallback_selectors
from cai_nghien_assistant.paths import NON_PATH_ENV_KEYS, configure_local_environment
from cai_nghien_assistant.retrieval import SearchIndex
from cai_nghien_assistant.schema import KnowledgeChunk
from cai_nghien_assistant.storage import RawDataExistsError, write_json_once


class GuardrailTests(unittest.TestCase):
    def load_runner(self):
        script_path = Path(__file__).resolve().parents[1] / "scripts" / "run_full_pipeline.py"
        spec = importlib.util.spec_from_file_location("run_full_pipeline_for_tests", script_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

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

    def test_audio_download_has_non_m4a_fallbacks(self) -> None:
        selectors = _fallback_selectors("audio", "bestaudio[ext=m4a]/bestaudio")
        self.assertEqual(selectors[0], "bestaudio[ext=m4a]/bestaudio")
        self.assertTrue(any("ext=webm" in selector for selector in selectors[1:]))
        self.assertTrue(any("best[height<=720]" in selector for selector in selectors[1:]))

    def test_runner_clears_stale_stage_error_on_recovery(self) -> None:
        runner = self.load_runner()
        video = {"stages": {"fetch-audio": {"status": "failed", "error": "fetch-audio return_code=0"}}}
        runner.mark_stage(video, "fetch-audio", "done", reason="artifact-present")
        self.assertNotIn("error", video["stages"]["fetch-audio"])

    def test_build_index_records_scalar_return_code(self) -> None:
        runner = self.load_runner()
        root = self.make_root()
        state_path = root / "state.json"
        state = {}

        class FakeLogger:
            def line(self, message: str) -> None:
                pass

        original_run_command = runner.run_command
        try:
            runner.run_command = lambda command, root, logger: (0, "Chunks indexed: 1\n")
            return_code = runner.build_index(types.SimpleNamespace(), root, FakeLogger(), state, state_path)
        finally:
            runner.run_command = original_run_command

        self.assertEqual(return_code, 0)
        self.assertEqual(state["index_runs"][-1]["status"], "done")
        self.assertEqual(state["index_runs"][-1]["return_code"], 0)

    def test_runner_default_catalog_includes_regular_and_livestream(self) -> None:
        runner = self.load_runner()
        root = self.make_root()
        catalog_path = root / "data" / "analysis" / "state" / "latest_catalog.jsonl"
        catalog_path.parent.mkdir(parents=True, exist_ok=True)
        rows = [
            {"video_id": "regular-1", "content_type": "regular"},
            {"video_id": "live-1", "content_type": "livestream"},
            {"video_id": "short-1", "content_type": "short"},
        ]
        catalog_path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

        selected_ids = [entry["video_id"] for entry in runner.catalog_entries(root, "regular+livestream")]
        self.assertEqual(set(selected_ids), {"regular-1", "live-1"})
        self.assertNotIn("short-1", selected_ids)

    def test_runner_default_stage_command_uses_combined_catalog_offsets(self) -> None:
        runner = self.load_runner()
        args = types.SimpleNamespace(root=Path("H:/cai-nghien-trading-local-rag"), content_type="regular+livestream")
        command = runner.stage_command(args, "fetch-audio", 193)
        self.assertNotIn("--content-type", command)

        args.content_type = "regular"
        command = runner.stage_command(args, "fetch-audio", 193)
        self.assertIn("--content-type", command)
        self.assertIn("regular", command)

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

    def test_chat_refuses_off_domain_partial_term_matches(self) -> None:
        root = self.make_root()
        index = SearchIndex.from_project(root)
        try:
            index.upsert_chunks(
                [
                    self.chunk(chunk_id="content:v1:pho", text="Cố mai làm bát phở rồi quay lại xem chart."),
                    self.chunk(chunk_id="content:v1:formula", text="Công thức chia vốn khi chạy bot DCA."),
                ]
            )
        finally:
            index.close()
        self.assertEqual(answer_question(root, "Công thức nấu phở bò là gì?"), UNKNOWN_ANSWER)

    def test_chat_answers_when_content_evidence_matches_question(self) -> None:
        root = self.make_root()
        index = SearchIndex.from_project(root)
        try:
            index.upsert_chunks(
                [
                    self.chunk(
                        chunk_id="content:v1:risk",
                        text="Quản trị rủi ro trong trade bot là chia vốn, kiểm soát lệnh và không all-in.",
                    )
                ]
            )
        finally:
            index.close()
        self.assertIn("Quản trị rủi ro", answer_question(root, "Quản trị rủi ro là gì?"))

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
