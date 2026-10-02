from __future__ import annotations

import unittest

from cai_nghien_assistant.schema import TranscriptSegment
from cai_nghien_assistant.speech_units import sentence_spans


def segment(video_id: str, start: float, end: float, text: str) -> TranscriptSegment:
    return TranscriptSegment(
        video_id=video_id,
        title=video_id,
        published_at="2026-01-01",
        start=start,
        end=end,
        text=text,
        source_type="transcript_approved",
        source_path=f"data/analysis/transcript_quality/{video_id}/approved.jsonl",
    )


class SpeechUnitTests(unittest.TestCase):
    def test_sentence_across_asr_segments_keeps_full_text_and_time(self) -> None:
        spans = sentence_spans(
            [
                segment("v1", 0, 4, "Nếu thị trường giảm thì"),
                segment("v1", 4, 8, "phải giữ vốn. Không mua vội."),
            ]
        )
        self.assertEqual([span.text for span in spans], ["Nếu thị trường giảm thì phải giữ vốn.", "Không mua vội."])
        self.assertEqual((spans[0].start, spans[0].end), (0, 8))

    def test_video_boundary_flushes_unfinished_sentence(self) -> None:
        spans = sentence_spans([segment("v1", 0, 4, "Còn dở"), segment("v2", 0, 4, "Ý mới.")])
        self.assertEqual([(span.video_id, span.text) for span in spans], [("v1", "Còn dở"), ("v2", "Ý mới.")])

    def test_no_punctuation_preserves_long_utterance(self) -> None:
        spans = sentence_spans([segment("v1", 0, 4, "Một câu"), segment("v1", 4, 8, "rất dài")])
        self.assertEqual(len(spans), 1)
        self.assertEqual(spans[0].text, "Một câu rất dài")

    def test_sentence_ending_inside_quotes_or_parentheses(self) -> None:
        spans = sentence_spans([segment("v1", 0, 4, 'Anh ấy nói "Dừng lại." (Tôi nghe rõ.) Sau đó đi.')])
        self.assertEqual(
            [span.text for span in spans],
            ['Anh ấy nói "Dừng lại."', '(Tôi nghe rõ.)', 'Sau đó đi.'],
        )


if __name__ == "__main__":
    unittest.main()
