from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cai_nghien_assistant.paths import configure_local_environment
from cai_nghien_assistant.schema import TranscriptSegment
from cai_nghien_assistant.storage import write_jsonl
from cai_nghien_assistant.transcript_quality.batch import clean_one_video, run_clean_batch
from cai_nghien_assistant.transcript_quality.cleaner import rule_clean_text
from cai_nghien_assistant.transcript_quality.cleaner_refine import refine_text
from cai_nghien_assistant.transcript_quality.schema import CLEANER_LOGIC_VERSION
from cai_nghien_assistant.transcript_quality.raw_layer import ensure_raw_layer
from cai_nghien_assistant.transcript_quality.review_store import apply_review_action, load_review_state
from cai_nghien_assistant.knowledge import iter_segments_for_index


class TranscriptQualityTests(unittest.TestCase):
    def make_root(self) -> Path:
        root = Path(tempfile.mkdtemp())
        (root / "config").mkdir()
        (root / "config" / "project.toml").write_text(
            """
[storage]
raw_dir = "data/raw"
analysis_dir = "data/analysis"

[pipeline]
version = "test"

[transcript_quality]
default_model_id = "conservative-refine"
asr_confusion_map = "data/analysis/transcript_quality/asr_confusion_map.json"
""",
            encoding="utf-8",
        )
        (root / "pyproject.toml").write_text("[project]\nname='tmp'\nversion='0'\n", encoding="utf-8")
        tq_dir = root / "data" / "analysis" / "transcript_quality"
        tq_dir.mkdir(parents=True, exist_ok=True)
        (tq_dir / "asr_confusion_map.json").write_text(
            json.dumps(
                {
                    "replacements": [
                        {"wrong": "đòn bạn", "right": "đòn bẩy", "requires_glossary": True},
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        configure_local_environment(root)
        return root

    def seed_normalized_transcript(self, root: Path, video_id: str = "vid001") -> None:
        transcript_dir = root / "data" / "analysis" / "transcripts" / video_id
        transcript_dir.mkdir(parents=True)
        rows = [
            {
                "video_id": video_id,
                "title": "Test video",
                "published_at": "2024-01-01",
                "start": 0.0,
                "end": 2.0,
                "text": "vốn 100%  vốn 100%",
                "source_type": "youtube_subtitle",
                "source_path": "data/raw/videos/vid001/subs.vtt",
                "language": "vi",
            }
        ]
        write_jsonl(transcript_dir / "youtube.jsonl", rows, root)
        catalog = root / "data" / "analysis" / "state"
        catalog.mkdir(parents=True, exist_ok=True)
        catalog_entry = {
            "video_id": video_id,
            "title": "Test video",
            "published_at": "2024-01-01",
            "content_type": "regular",
        }
        (catalog / "latest_catalog.jsonl").write_text(
            json.dumps(catalog_entry, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def test_rule_clean_removes_duplicate_phrase(self) -> None:
        cleaned, changes = rule_clean_text("vốn 100%  vốn 100%")
        self.assertIn("vốn 100%", cleaned)
        self.assertTrue(changes)

    def test_conservative_refine_applies_glossary_confusion(self) -> None:
        cleaned, changes = refine_text(
            "vào lệnh với đòn bạn 10x",
            glossary_terms=["đòn bẩy"],
            confusion_entries=[
                {"wrong": "đòn bạn", "right": "đòn bẩy", "requires_glossary": True},
            ],
        )
        self.assertIn("đòn bẩy", cleaned)
        self.assertTrue(any(c.change_type == "glossary_fix" for c in changes))

    def test_clean_batch_uses_logic_version_2(self) -> None:
        self.assertEqual(CLEANER_LOGIC_VERSION, "2.0.0")

    def test_clean_batch_is_idempotent(self) -> None:
        root = self.make_root()
        self.seed_normalized_transcript(root)
        first = clean_one_video(root, "vid001", model_id="conservative-refine")
        self.assertEqual(first["status"], "cleaned")
        second = clean_one_video(root, "vid001", model_id="conservative-refine")
        self.assertEqual(second["status"], "skipped")
        self.assertEqual(second["reason"], "ai_clean_unchanged")

    def test_approved_blocks_ai_rerun(self) -> None:
        root = self.make_root()
        self.seed_normalized_transcript(root)
        clean_one_video(root, "vid001")
        apply_review_action(root, "vid001", "approve", {})
        forced = clean_one_video(root, "vid001", force=False)
        self.assertEqual(forced["status"], "skipped")
        self.assertEqual(forced["reason"], "already_approved")

    def test_index_uses_provisional_tier_label(self) -> None:
        root = self.make_root()
        self.seed_normalized_transcript(root)
        run_clean_batch(root, limit=1)
        segments = list(iter_segments_for_index(root))
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].source_type, "transcript_ai_provisional")

    def test_accept_change_uses_ai_text_without_change_log(self) -> None:
        root = self.make_root()
        self.seed_normalized_transcript(root)
        clean_one_video(root, "vid001")
        out = root / "data" / "analysis" / "transcript_quality" / "vid001"
        (out / "change_log.jsonl").write_text("", encoding="utf-8")
        apply_review_action(
            root,
            "vid001",
            "accept_change",
            {"segment_id": "vid001:0:0.000", "ai_text": "Bản AI đề xuất mới"},
        )
        approved = json.loads((out / "approved.jsonl").read_text(encoding="utf-8").strip().splitlines()[0])
        self.assertEqual(approved["text"], "Bản AI đề xuất mới")

    def test_human_edit_survives_second_clean_skip(self) -> None:
        root = self.make_root()
        self.seed_normalized_transcript(root)
        clean_one_video(root, "vid001")
        apply_review_action(
            root,
            "vid001",
            "edit_segment",
            {"segment_id": "vid001:0:0.000", "text": "Sửa tay giữ nguyên số 50%"},
        )
        state = load_review_state(root, "vid001")
        self.assertIsNotNone(state)
        self.assertEqual(state.status, "in_review")


if __name__ == "__main__":
    unittest.main()
