"""Export the playbook to a static GitHub Pages site under docs/."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

from ..config import load_project_config
from ..paths import configure_local_environment
from ..storage import atomic_write_text
from .paths import playbook_dir

HEADING_RE = re.compile(r"^(#{1,3})\s+(.*)$")
LIST_RE = re.compile(r"^[-*]\s+(.*)$")
CODE_RE = re.compile(r"`([^`]+)`")
BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")


def inline_format(text: str) -> str:
    escaped = html.escape(text, quote=False)
    escaped = CODE_RE.sub(r"<code>\1</code>", escaped)
    escaped = BOLD_RE.sub(r"<strong>\1</strong>", escaped)
    return escaped


def markdown_to_html(markdown: str) -> str:
    lines = markdown.replace("\r\n", "\n").split("\n")
    blocks: list[str] = []
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        if not stripped:
            index += 1
            continue
        heading = HEADING_RE.match(stripped)
        if heading:
            level = len(heading.group(1))
            blocks.append(f"<h{level}>{inline_format(heading.group(2).strip())}</h{level}>")
            index += 1
            continue
        listed = LIST_RE.match(stripped)
        if listed:
            items: list[str] = []
            while index < len(lines):
                item = LIST_RE.match(lines[index].strip())
                if not item:
                    break
                items.append(f"<li>{inline_format(item.group(1))}</li>")
                index += 1
            blocks.append("<ul>\n" + "\n".join(items) + "\n</ul>")
            continue
        para = [stripped]
        index += 1
        while index < len(lines):
            nxt = lines[index].strip()
            if not nxt or HEADING_RE.match(nxt) or LIST_RE.match(nxt):
                break
            para.append(nxt)
            index += 1
        blocks.append("<p>" + inline_format(" ".join(para)) + "</p>")
    return "\n".join(blocks)


def _page_html(*, title: str, asset_prefix: str, body: str, extra_script: str = "") -> str:
    script_tag = f'\n    <script src="{asset_prefix}assets/ask.js"></script>' if extra_script else ""
    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <link rel="stylesheet" href="{asset_prefix}assets/style.css">
</head>
<body>
  <header class="wrap">
    <p class="brand"><a href="{asset_prefix}index.html">Cai Nghện Trading — sách kiến thức</a></p>
    <p class="note">Giáo dục / tham khảo — không phải lời khuyên đầu tư. Không hướng dẫn giao dịch trên sàn chưa được Bộ Tài chính cấp phép.</p>
  </header>
  <main class="wrap">
{body}
  </main>
  <footer class="wrap">
    <p>Không phải tư vấn pháp lý.</p>
  </footer>{script_tag}
</body>
</html>
"""


def _home_body(chapters: list[dict[str, Any]]) -> str:
    items = []
    for row in chapters:
        href = f"chapters/{Path(str(row['file'])).stem}.html"
        title = html.escape(str(row.get("title") or row["file"]))
        items.append(f'      <li><a href="{href}">{title}</a></li>')
    toc = "\n".join(items)
    return f"""    <h1>Sách kiến thức</h1>
    <p>Gõ câu hỏi. Trang mở chương liên quan.</p>
    <form id="ask-form">
      <label for="ask-q">Hỏi</label>
      <input id="ask-q" name="q" type="search" placeholder="Ví dụ: Quỹ khẩn cấp? Sàn crypto Việt Nam?" autocomplete="off">
      <button type="submit">Xem chương</button>
    </form>
    <div id="answer" hidden></div>
    <h2>Mục lục</h2>
    <ol class="toc">
{toc}
    </ol>
"""


STYLE_CSS = """:root {
  color-scheme: light;
  --bg: #f6f3ee;
  --ink: #1c1917;
  --muted: #57534e;
  --card: #fffdf8;
  --line: #d6d3d1;
  --accent: #9a3412;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: "Segoe UI", "Noto Sans", sans-serif;
  background: var(--bg);
  color: var(--ink);
  line-height: 1.55;
}
.wrap { max-width: 44rem; margin: 0 auto; padding: 1rem 1.1rem; }
header.wrap { padding-top: 1.4rem; }
.brand { font-weight: 700; margin: 0 0 0.25rem; }
.brand a { color: inherit; text-decoration: none; }
.note, footer { color: var(--muted); font-size: 0.92rem; }
h1, h2, h3 { line-height: 1.25; }
a { color: var(--accent); }
form {
  display: grid;
  gap: 0.5rem;
  margin: 1rem 0 1.2rem;
  padding: 0.9rem;
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 10px;
}
input[type="search"] {
  width: 100%;
  padding: 0.65rem 0.7rem;
  font: inherit;
  border: 1px solid var(--line);
  border-radius: 8px;
}
button {
  justify-self: start;
  padding: 0.5rem 0.9rem;
  font: inherit;
  color: #fff;
  background: var(--accent);
  border: 0;
  border-radius: 8px;
  cursor: pointer;
}
#answer {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 0.9rem 1rem;
  margin-bottom: 1.5rem;
}
.toc { padding-left: 1.2rem; }
code {
  font-size: 0.92em;
  background: #efebe4;
  padding: 0.05rem 0.3rem;
  border-radius: 4px;
}
ul { padding-left: 1.2rem; }
"""

ASK_JS = """async function loadPages() {
  const response = await fetch("pages.json");
  if (!response.ok) {
    throw new Error("Không tải được pages.json");
  }
  return response.json();
}

function escapeRegex(text) {
  const specials = ".*+?^${}()|[]\\\\";
  let out = "";
  for (const ch of text) {
    if (specials.includes(ch)) {
      out += "\\\\" + ch;
    } else {
      out += ch;
    }
  }
  return out;
}

function keywordInQuestion(needle, lowered) {
  if (needle.length <= 3) {
    const re = new RegExp(
      "(?<![a-zà-ỹ0-9])" + escapeRegex(needle) + "(?![a-zà-ỹ0-9])",
      "i"
    );
    return re.test(lowered);
  }
  return lowered.includes(needle);
}

function chapterScore(question, chapter) {
  const lowered = question.toLowerCase();
  let hits = 0;
  for (const keyword of chapter.keywords || []) {
    const needle = String(keyword).trim().toLowerCase();
    if (needle.length >= 2 && keywordInQuestion(needle, lowered)) {
      hits += 1;
    }
  }
  const titleWords = String(chapter.title || "")
    .toLowerCase()
    .split(/\\s+/)
    .filter((word) => word.length >= 4);
  for (const word of titleWords) {
    if (lowered.includes(word)) {
      hits += 1;
    }
  }
  return hits;
}

function chooseChapters(question, chapters, maxChapters) {
  const scored = [];
  for (const chapter of chapters) {
    const score = chapterScore(question, chapter);
    if (score > 0) {
      scored.push([score, chapter]);
    }
  }
  scored.sort((a, b) => b[0] - a[0]);
  if (scored.length === 0) {
    return [];
  }
  const best = scored[0][0];
  const chosen = [];
  for (const [score, chapter] of scored) {
    if (score !== best) {
      break;
    }
    chosen.push(chapter);
    if (chosen.length >= maxChapters) {
      break;
    }
  }
  return chosen;
}

function showAnswer(html) {
  const box = document.getElementById("answer");
  box.hidden = false;
  box.innerHTML = html;
}

async function onAsk(event) {
  event.preventDefault();
  const input = document.getElementById("ask-q");
  const question = (input.value || "").trim();
  const data = await loadPages();
  const unknown = data.unknown_answer || "Tôi không biết dựa trên dữ liệu đã phân tích từ kênh này.";
  if (!question) {
    showAnswer("<p>" + unknown + "</p>");
    return;
  }
  const chosen = chooseChapters(question, data.chapters || [], 2);
  if (chosen.length === 0) {
    showAnswer("<p>" + unknown + "</p>");
    return;
  }
  const parts = chosen.map((chapter) => {
    const link = chapter.href
      ? '<p><a href="' + chapter.href + '">Mở trang chương</a></p>'
      : "";
    return link + (chapter.html || "");
  });
  showAnswer(parts.join("<hr>"));
}

function handleAskError(err) {
  showAnswer("<p>Không hỏi được: " + String(err.message || err) + "</p>");
}

const form = document.getElementById("ask-form");
if (form) {
  form.addEventListener("submit", (event) => {
    onAsk(event).catch(handleAskError);
  });
  const query = new URLSearchParams(window.location.search).get("q");
  if ((query || "").trim()) {
    onAsk({ preventDefault() {} }).catch(handleAskError);
  }
}
"""


def export_playbook_pages(root: str | Path | None = None) -> dict[str, Any]:
    root_path = Path(root or ".").resolve()
    configure_local_environment(root_path)
    source = playbook_dir(root_path)
    catalog_path = source / "index.json"
    if not catalog_path.exists():
        raise FileNotFoundError(f"Missing playbook index: {catalog_path}")
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    chapters = list(catalog.get("chapters") or [])
    config = load_project_config(root_path)
    unknown = str(config.get("guardrails", {}).get("unknown_answer") or "")

    docs = root_path / "docs"
    (docs / "assets").mkdir(parents=True, exist_ok=True)
    (docs / "chapters").mkdir(parents=True, exist_ok=True)
    (docs / "playbook").mkdir(parents=True, exist_ok=True)

    pages_chapters: list[dict[str, Any]] = []
    written = 0
    for row in chapters:
        file_name = str(row.get("file") or "")
        md_path = source / file_name
        if not md_path.exists():
            continue
        markdown = md_path.read_text(encoding="utf-8")
        body_html = markdown_to_html(markdown)
        stem = Path(file_name).stem
        href = f"chapters/{stem}.html"
        title = str(row.get("title") or stem)
        page = _page_html(
            title=title,
            asset_prefix="../",
            body=f"    <p><a href=\"../index.html\">← Mục lục</a></p>\n    {body_html}",
        )
        atomic_write_text(docs / "chapters" / f"{stem}.html", page, root_path)
        atomic_write_text(docs / "playbook" / file_name, markdown, root_path)
        pages_chapters.append(
            {
                "topic_id": row.get("topic_id"),
                "title": title,
                "file": file_name,
                "keywords": row.get("keywords") or [],
                "href": href,
                "html": body_html,
            }
        )
        written += 1

    keep_stems = {Path(str(row.get("file") or "")).stem for row in chapters if row.get("file")}
    keep_stems.add("index")
    for folder, pattern in ((docs / "chapters", "*.html"), (docs / "playbook", "*.md")):
        if not folder.exists():
            continue
        for path in folder.glob(pattern):
            if path.stem not in keep_stems:
                path.unlink()

    home = _page_html(
        title="Cai Nghện Trading — sách kiến thức",
        asset_prefix="",
        body=_home_body(pages_chapters),
        extra_script="ask.js",
    )
    atomic_write_text(docs / "index.html", home, root_path)
    atomic_write_text(docs / "assets" / "style.css", STYLE_CSS, root_path)
    atomic_write_text(docs / "assets" / "ask.js", ASK_JS, root_path)
    atomic_write_text(docs / ".nojekyll", "", root_path)
    atomic_write_text(
        docs / "playbook" / "index.json",
        json.dumps({"chapters": chapters}, ensure_ascii=False, indent=2) + "\n",
        root_path,
    )
    pages_payload = {"unknown_answer": unknown, "chapters": pages_chapters}
    atomic_write_text(
        docs / "pages.json",
        json.dumps(pages_payload, ensure_ascii=False, indent=2) + "\n",
        root_path,
    )
    return {"chapters_written": written, "docs": "docs"}
