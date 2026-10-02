from __future__ import annotations

import unittest
import json
import tempfile
from pathlib import Path

from cai_nghien_assistant.youtube_collect import filter_catalog_entries, restore_raw_catalog, sort_oldest_first


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

    def test_restore_catalog_uses_widest_raw_snapshot(self) -> None:
        root = Path(tempfile.mkdtemp())
        (root / "config").mkdir()
        (root / "config" / "project.toml").write_text(
            '[storage]\nraw_dir = "data/raw"\nanalysis_dir = "data/analysis"\n', encoding="utf-8"
        )
        raw_dir = root / "data/raw/catalog"
        raw_dir.mkdir(parents=True)
        (raw_dir / "catalog-20260101T000000Z.jsonl").write_text(
            '{"video_id":"old"}\n{"video_id":"new"}\n', encoding="utf-8"
        )
        (raw_dir / "catalog-20260102T000000Z.jsonl").write_text('{"video_id":"new"}\n', encoding="utf-8")
        count = restore_raw_catalog(root)
        target = root / "data/analysis/state/latest_catalog.jsonl"
        self.assertEqual(count, 2)
        self.assertEqual(
            {json.loads(line)["video_id"] for line in target.read_text(encoding="utf-8").splitlines()},
            {"old", "new"},
        )
        with self.assertRaises(FileExistsError):
            restore_raw_catalog(root)


if __name__ == "__main__":
    unittest.main()
