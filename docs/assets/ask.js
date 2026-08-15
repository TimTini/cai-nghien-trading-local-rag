async function loadPages() {
  const response = await fetch("pages.json");
  if (!response.ok) {
    throw new Error("Không tải được pages.json");
  }
  return response.json();
}

function keywordInQuestion(needle, lowered) {
  if (needle.length <= 3) {
    const escaped = needle.replace(/[.*+?^${}()|[\]\]/g, "\$&");
    const re = new RegExp("(?<![a-zà-ỹ0-9])" + escaped + "(?![a-zà-ỹ0-9])", "i");
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
    .split(/\s+/)
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

const form = document.getElementById("ask-form");
if (form) {
  form.addEventListener("submit", (event) => {
    onAsk(event).catch((err) => {
      showAnswer("<p>Không hỏi được: " + String(err.message || err) + "</p>");
    });
  });
}
