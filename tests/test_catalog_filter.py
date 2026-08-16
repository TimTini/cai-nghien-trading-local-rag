from __future__ import annotations

import unittest

from cai_nghien_assistant.youtube_collect import filter_catalog_entries, sort_oldest_first


class CatalogFilterTests(unittest.TestCase):
    def sample(self) -> list[dict]:
        return sort_oldest_first(
            [
                {"video_id": "a", "published_at": "2025-12-01", "content_type": "regular"},
                {"video_id": "b", "published_at": "2026-01-15", "content_type": "regular"},
                {"video_id": "c", "published_at": "2026-03-01", "content_type": "livestream"},
                {"video_id": "d", "published_at": "2026-04-01", "content_type": "short"},
            ]
        )

    def test_filter_year_2026(self) -> None:
        rows = filter_catalog_entries(self.sample(), published_year=2026)
        self.assertEqual([row["video_id"] for row in rows], ["b", "c", "d"])

    def test_filter_year_and_content_type(self) -> None:
        rows = filter_catalog_entries(
            self.sample(),
            content_types=("regular", "livestream"),
            published_year=2026,
        )
        self.assertEqual([row["video_id"] for row in rows], ["b", "c"])


if __name__ == "__main__":
    unittest.main()
