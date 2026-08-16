from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from cai_nghien_assistant.paths import configure_local_environment
from cai_nghien_assistant.playbook.pages import export_playbook_pages, markdown_to_html


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


class PlaybookPagesTests(unittest.TestCase):
    def test_markdown_to_html_keeps_heading_and_list(self) -> None:
        html = markdown_to_html(
            "# Quản trị vốn\n\nĐặt **stop loss** trước khi vào.\n\n- Điều kiện: futures\n- Ngoại lệ: spot\n"
        )
        self.assertIn("<h1>Quản trị vốn</h1>", html)
        self.assertIn("<strong>stop loss</strong>", html)
        self.assertIn("<li>Điều kiện: futures</li>", html)
        self.assertIn("<li>Ngoại lệ: spot</li>", html)

    def test_export_writes_docs_site(self) -> None:
        root = make_root()
        playbook = root / "data" / "analysis" / "knowledge" / "playbook"
        playbook.mkdir(parents=True, exist_ok=True)
        (playbook / "quan-ly-von.md").write_text(
            "# Quản trị vốn\n\nChỉ tạo bot với số chấp nhận mất hết.\n",
            encoding="utf-8",
        )
        (playbook / "index.json").write_text(
            json.dumps(
                {
                    "chapters": [
                        {
                            "topic_id": "quan_ly_von",
                            "title": "Quản trị vốn và rủi ro",
                            "file": "quan-ly-von.md",
                            "keywords": ["rủi ro", "ký quỹ", "vốn"],
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = export_playbook_pages(root)
        docs = root / "docs"
        self.assertTrue((docs / "index.html").exists())
        self.assertTrue((docs / "assets" / "ask.js").exists())
        self.assertTrue((docs / "assets" / "style.css").exists())
        self.assertTrue((docs / ".nojekyll").exists())
        chapter_html = (docs / "chapters" / "quan-ly-von.html").read_text(encoding="utf-8")
        self.assertIn("Chỉ tạo bot với số chấp nhận mất hết", chapter_html)
        home = (docs / "index.html").read_text(encoding="utf-8")
        self.assertIn("Quản trị vốn và rủi ro", home)
        pages = json.loads((docs / "pages.json").read_text(encoding="utf-8"))
        self.assertEqual(pages["chapters"][0]["topic_id"], "quan_ly_von")
        self.assertIn("Chỉ tạo bot", pages["chapters"][0]["html"])
        self.assertEqual(result["chapters_written"], 1)
        leftover = docs / "chapters" / "bot-luoi.html"
        leftover.write_text("old how-to", encoding="utf-8")
        export_playbook_pages(root)
        self.assertFalse(leftover.exists())

    def test_exported_ask_js_is_valid_javascript(self) -> None:
        root = make_root()
        playbook = root / "data" / "analysis" / "knowledge" / "playbook"
        playbook.mkdir(parents=True, exist_ok=True)
        (playbook / "oi.md").write_text("# Open Interest (OI)\n\nOI là số liệu.\n", encoding="utf-8")
        (playbook / "index.json").write_text(
            json.dumps(
                {
                    "chapters": [
                        {
                            "topic_id": "oi",
                            "title": "Open Interest (OI)",
                            "file": "oi.md",
                            "keywords": ["oi", "open interest"],
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        export_playbook_pages(root)
        ask_js = root / "docs" / "assets" / "ask.js"
        result = subprocess.run(
            ["node", "--check", str(ask_js)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_exported_ask_js_reads_q_from_url(self) -> None:
        root = make_root()
        playbook = root / "data" / "analysis" / "knowledge" / "playbook"
        playbook.mkdir(parents=True, exist_ok=True)
        (playbook / "oi.md").write_text("# Open Interest (OI)\n\nOI là số liệu.\n", encoding="utf-8")
        (playbook / "index.json").write_text(
            json.dumps(
                {
                    "chapters": [
                        {
                            "topic_id": "oi",
                            "title": "Open Interest (OI)",
                            "file": "oi.md",
                            "keywords": ["oi"],
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        export_playbook_pages(root)
        text = (root / "docs" / "assets" / "ask.js").read_text(encoding="utf-8")
        self.assertIn("URLSearchParams", text)
        self.assertIn('get("q")', text)


if __name__ == "__main__":
    unittest.main()
