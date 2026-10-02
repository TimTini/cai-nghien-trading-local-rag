from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cai_nghien_assistant.paths import configure_local_environment
from cai_nghien_assistant.playbook.ask import ask_playbook
from cai_nghien_assistant.playbook.assemble import assemble_video_sources, render_source_markdown
from cai_nghien_assistant.playbook.compile import append_chapter_update
from cai_nghien_assistant.playbook.router import choose_chapters
from cai_nghien_assistant.playbook.schema import Chapter, PlaybookRule, VideoArticle
from cai_nghien_assistant.schema import TranscriptSegment


def make_root() -> Path:
    root = Path(tempfile.mkdtemp())
    (root / "config").mkdir()
    (root / "config" / "project.toml").write_text(
        """
[pipeline]
version = "0.1.0"

[storage]
analysis_dir = "data/analysis"

[guardrails]
unknown_answer = "Tôi không biết dựa trên dữ liệu đã phân tích từ kênh này."

[playbook]
output_dir = "data/analysis/knowledge"
""",
        encoding="utf-8",
    )
    (root / "pyproject.toml").write_text("[project]\nname='tmp'\nversion='0'\n", encoding="utf-8")
    configure_local_environment(root)
    return root


def make_segment(
    *,
    video_id: str = "v1",
    start: float = 0.0,
    end: float = 5.0,
    text: str = "Nên đặt stop loss khi trade futures.",
    title: str = "Risk",
) -> TranscriptSegment:
    return TranscriptSegment(
        video_id=video_id,
        title=title,
        published_at="2026-01-01",
        start=start,
        end=end,
        text=text,
        source_type="transcript_approved",
        source_path=f"data/analysis/transcript_quality/{video_id}/approved.jsonl",
    )


class PlaybookAssembleTests(unittest.TestCase):
    def test_source_shows_sentence_across_asr_segments_as_one_paragraph(self) -> None:
        markdown = render_source_markdown(
            video_id="v1",
            title="Risk",
            published_at="2026-01-01",
            source_type="transcript_approved",
            segments=[
                make_segment(start=0, end=4, text="Nếu thị trường giảm thì"),
                make_segment(start=4, end=8, text="phải giữ vốn."),
            ],
        )
        self.assertIn("[00:00] Nếu thị trường giảm thì phải giữ vốn.", markdown)
        self.assertNotIn("[00:04] phải giữ vốn.", markdown)

    def test_source_keeps_full_text_in_time_order(self) -> None:
        segments = [
            make_segment(start=10.0, end=20.0, text="Trừ khi thị trường sideway thì không vào."),
            make_segment(start=0.0, end=10.0, text="Nên đặt stop loss 2% khi trade futures."),
        ]
        markdown = render_source_markdown(
            video_id="v1",
            title="Risk",
            published_at="2026-01-01",
            source_type="transcript_approved",
            segments=segments,
            ocr_lines=["R:R 1:2"],
        )
        first = markdown.find("Nên đặt stop loss 2% khi trade futures.")
        second = markdown.find("Trừ khi thị trường sideway thì không vào.")
        self.assertNotEqual(first, -1)
        self.assertNotEqual(second, -1)
        self.assertLess(first, second)
        self.assertIn("00:00", markdown)
        self.assertIn("00:10", markdown)
        self.assertIn("R:R 1:2", markdown)
        self.assertIn("OCR", markdown)

    def test_assemble_writes_one_source_file_per_video(self) -> None:
        root = make_root()
        transcript_dir = root / "data" / "analysis" / "transcripts" / "v1"
        transcript_dir.mkdir(parents=True)
        rows = [
            {
                "video_id": "v1",
                "title": "Risk",
                "published_at": "2026-01-01",
                "start": 0.0,
                "end": 8.0,
                "text": "Quản trị vốn khi trade crypto là điều bắt buộc. Không được bỏ stop loss.",
                "source_type": "youtube_subtitle",
                "source_path": "data/analysis/transcripts/v1/youtube.jsonl",
            }
        ]
        (transcript_dir / "youtube.jsonl").write_text(
            "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
            encoding="utf-8",
        )
        (root / "data" / "analysis" / "state").mkdir(parents=True, exist_ok=True)
        (root / "data" / "analysis" / "state" / "latest_catalog.jsonl").write_text(
            json.dumps(
                {
                    "video_id": "v1",
                    "title": "Risk",
                    "published_at": "2026-01-01",
                    "content_type": "regular",
                }
            )
            + "\n",
            encoding="utf-8",
        )

        result = assemble_video_sources(root, limit=1, force=True)
        source_path = root / "data" / "analysis" / "knowledge" / "videos" / "v1" / "source.md"
        self.assertTrue(source_path.exists())
        text = source_path.read_text(encoding="utf-8")
        self.assertIn("Không được bỏ stop loss", text)
        self.assertEqual(result["videos_written"], 1)


class PlaybookSchemaTests(unittest.TestCase):
    def test_rule_keeps_conditions_and_exceptions(self) -> None:
        rule = PlaybookRule(
            rule_id="r1",
            text="Đặt stop loss 2% khi vào futures, trừ khi đang sideway thì đứng ngoài.",
            conditions=["vào lệnh futures"],
            exceptions=["thị trường sideway thì không vào"],
            start=12.0,
            end=40.0,
            evidence_quote="Nên đặt stop loss 2% khi trade futures. Trừ khi sideway thì không vào.",
            kind="doctrine",
        )
        payload = rule.to_dict()
        self.assertEqual(payload["conditions"], ["vào lệnh futures"])
        self.assertEqual(payload["exceptions"], ["thị trường sideway thì không vào"])
        self.assertEqual(payload["kind"], "doctrine")

        article = VideoArticle(
            video_id="v1",
            title="Risk",
            published_at="2026-01-01",
            source_type="transcript_approved",
            thesis="Quản trị vốn trước khi vào lệnh.",
            rules=[rule],
            topics=["risk"],
        )
        self.assertEqual(article.to_dict()["rules"][0]["text"], rule.text)


class PlaybookRouterAskTests(unittest.TestCase):
    def test_choose_chapters_matches_topic_keywords(self) -> None:
        chapters = [
            Chapter(
                topic_id="risk",
                title="Quản trị vốn và rủi ro",
                keywords=["rủi ro", "stop loss", "vốn", "margin"],
                path="playbook/risk.md",
                body="Đặt stop loss trước khi vào lệnh.",
            ),
            Chapter(
                topic_id="mindset",
                title="Tâm lý giao dịch",
                keywords=["tâm lý", "FOMO", "kỷ luật"],
                path="playbook/mindset.md",
                body="Không vào lệnh vì FOMO.",
            ),
        ]
        chosen = choose_chapters("Anh nói gì về stop loss?", chapters)
        self.assertEqual([item.topic_id for item in chosen], ["risk"])

    def test_short_keyword_does_not_match_inside_another_word(self) -> None:
        chapters = [
            Chapter(
                topic_id="oi",
                title="Open Interest",
                keywords=["oi", "volume"],
                path="playbook/oi.md",
                body="OI khac volume.",
            ),
            Chapter(
                topic_id="bot",
                title="Bot luoi",
                keywords=["bot", "luoi"],
                path="playbook/bot.md",
                body="Bot luoi ke san muc gia.",
            ),
        ]
        chosen = choose_chapters("Bot luoi la gi?", chapters)
        self.assertEqual([item.topic_id for item in chosen], ["bot"])
        chosen_oi = choose_chapters("Thông số OI", chapters)
        self.assertEqual([item.topic_id for item in chosen_oi], ["oi"])

    def test_ask_returns_full_chapter(self) -> None:
        root = make_root()
        playbook_dir = root / "data" / "analysis" / "knowledge" / "playbook"
        playbook_dir.mkdir(parents=True, exist_ok=True)
        body = (
            "# Quản trị vốn và rủi ro\n\n"
            "Đặt stop loss 2% khi vào futures.\n"
            "Trừ khi thị trường sideway thì đứng ngoài, không cắt lệnh lung tung.\n"
        )
        (playbook_dir / "risk.md").write_text(body, encoding="utf-8")
        (playbook_dir / "index.json").write_text(
            json.dumps(
                {
                    "chapters": [
                        {
                            "topic_id": "risk",
                            "title": "Quản trị vốn và rủi ro",
                            "file": "risk.md",
                            "keywords": ["rủi ro", "stop loss", "vốn"],
                        }
                    ]
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        answer = ask_playbook(root, "Stop loss khi futures thì sao?")
        self.assertIn("Đặt stop loss 2%", answer)
        self.assertIn("Trừ khi thị trường sideway", answer)

    def test_ask_unknown_when_no_chapter_matches(self) -> None:
        root = make_root()
        playbook_dir = root / "data" / "analysis" / "knowledge" / "playbook"
        playbook_dir.mkdir(parents=True, exist_ok=True)
        (playbook_dir / "index.json").write_text(
            json.dumps({"chapters": []}, ensure_ascii=False),
            encoding="utf-8",
        )
        answer = ask_playbook(root, "Chiến lược options trên NASDAQ?")
        self.assertEqual(answer, "Tôi không biết dựa trên dữ liệu đã phân tích từ kênh này.")


class PlaybookCompileTests(unittest.TestCase):
    def test_append_update_keeps_existing_chapter(self) -> None:
        root = make_root()
        path = root / "data" / "analysis" / "knowledge" / "playbook" / "risk.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        original = "# Quản trị vốn\n\nĐặt stop loss trước khi vào lệnh.\n"
        path.write_text(original, encoding="utf-8")
        append_chapter_update(
            path,
            root,
            heading="Cập nhật từ video v2 (2026-03-01)",
            body="Thêm: không tăng volume khi đang thua.",
        )
        text = path.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# Quản trị vốn"))
        self.assertIn("Đặt stop loss trước khi vào lệnh.", text)
        self.assertIn("Cập nhật từ video v2", text)
        self.assertIn("không tăng volume khi đang thua", text)


if __name__ == "__main__":
    unittest.main()
