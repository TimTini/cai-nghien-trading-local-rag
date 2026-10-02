from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cai_nghien_assistant.knowledge_extraction.extractor import (
    classify_sentence,
    facts_from_segment,
    facts_from_segments,
    split_sentences,
)
from cai_nghien_assistant.knowledge_extraction.batch import run_extract_batch
from cai_nghien_assistant.paths import configure_local_environment
from cai_nghien_assistant.schema import TranscriptSegment


class KnowledgeExtractionTests(unittest.TestCase):
    def make_root(self) -> Path:
        root = Path(tempfile.mkdtemp())
        (root / "config").mkdir()
        (root / "config" / "project.toml").write_text(
            """
[pipeline]
version = "0.1.0"

[storage]
analysis_dir = "data/analysis"

[knowledge_extraction]
output_dir = "data/analysis/knowledge"
min_sentence_chars = 15
require_domain_term = true
include_ocr = false
""",
            encoding="utf-8",
        )
        (root / "pyproject.toml").write_text("[project]\nname='tmp'\nversion='0'\n", encoding="utf-8")
        configure_local_environment(root)
        return root

    def test_split_and_classify(self) -> None:
        sentences = split_sentences("Quản trị rủi ro là quan trọng. Nên đặt stop loss 2%.")
        self.assertEqual(len(sentences), 2)
        self.assertEqual(classify_sentence("Nên đặt stop loss 2%"), "metric")
        self.assertEqual(classify_sentence("DCA là gì"), "definition")

    def test_facts_from_segment_requires_domain_term(self) -> None:
        segment = TranscriptSegment(
            video_id="v1",
            title="Test",
            published_at="2024-01-01",
            start=10.0,
            end=20.0,
            text="Hôm nay trời đẹp. Nên đặt stop loss khi trade futures.",
            source_type="transcript_approved",
            source_path="data/analysis/transcript_quality/v1/approved.jsonl",
        )
        facts = facts_from_segment(
            segment,
            terms={"stop loss", "trade", "futures"},
            pipeline_version="0.1.0",
            min_chars=15,
            require_domain_term=True,
        )
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0].category, "guidance")
        self.assertEqual(facts[0].evidence_quote, facts[0].fact_text)

    def test_fact_does_not_end_at_asr_segment_boundary(self) -> None:
        first = TranscriptSegment("v1", "Test", "2026-01-01", 0, 4, "Nếu bot giảm thì", "transcript_approved", "approved.jsonl")
        second = TranscriptSegment("v1", "Test", "2026-01-01", 4, 8, "phải giữ vốn.", "transcript_approved", "approved.jsonl")
        facts = facts_from_segments([first, second], self.make_root(), min_chars=15, require_domain_term=False)
        self.assertEqual([fact.fact_text for fact in facts], ["Nếu bot giảm thì phải giữ vốn."])
        self.assertEqual((facts[0].start, facts[0].end), (0, 8))

    def test_batch_writes_corpus(self) -> None:
        root = self.make_root()
        transcript_dir = root / "data" / "analysis" / "transcripts" / "v1"
        transcript_dir.mkdir(parents=True)
        row = {
            "video_id": "v1",
            "title": "Risk",
            "published_at": "2024-01-01",
            "start": 0.0,
            "end": 5.0,
            "text": "Quản trị vốn khi trade crypto là điều bắt buộc.",
            "source_type": "youtube_subtitle",
            "source_path": "data/analysis/transcripts/v1/youtube.jsonl",
        }
        (transcript_dir / "youtube.jsonl").write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
        (root / "data" / "analysis" / "state").mkdir(parents=True, exist_ok=True)
        (root / "data" / "analysis" / "state" / "latest_catalog.jsonl").write_text(
            json.dumps({"video_id": "v1", "title": "Risk", "published_at": "2024-01-01", "content_type": "regular"})
            + "\n",
            encoding="utf-8",
        )

        result = run_extract_batch(root, limit=1)
        self.assertEqual(result["videos_processed"], 1)
        self.assertGreaterEqual(result["total_facts"], 1)

        corpus_path = root / "data" / "analysis" / "knowledge" / "corpus.jsonl"
        self.assertTrue(corpus_path.exists())
        first_line = json.loads(corpus_path.read_text(encoding="utf-8").splitlines()[0])
        self.assertIn("fact_id", first_line)
        self.assertIn("evidence_quote", first_line)


if __name__ == "__main__":
    unittest.main()
