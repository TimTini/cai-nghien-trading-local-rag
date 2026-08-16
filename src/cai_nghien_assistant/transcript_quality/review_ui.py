"""UI review transcript local — stdlib HTTP, không phụ thuộc cloud."""

from __future__ import annotations

import json
import mimetypes
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from ..config import load_project_config
from ..media import first_media_file
from ..paths import configure_local_environment, resolve_project_root, to_project_relative
from ..storage import read_jsonl
from .raw_layer import ordered_video_ids_with_transcripts, quality_dir
from .review_store import apply_review_action, list_history_files, load_review_state


def _media_url(root: Path, video_id: str, media_kind: str) -> str | None:
    path = first_media_file(root, video_id, media_kind)
    if path is None:
        return None
    rel = to_project_relative(path, root)
    return "/media/" + urllib.parse.quote(rel.replace("\\", "/"), safe="/:")


def _video_list_payload(root: Path) -> list[dict[str, Any]]:
    items = []
    for video_id in ordered_video_ids_with_transcripts(root):
        state = load_review_state(root, video_id)
        status = state.status if state else "pending_ai"
        title = state.title if state else video_id
        published_at = state.published_at if state else ""
        suspicious = state.suspicious_count if state else 0
        items.append(
            {
                "video_id": video_id,
                "title": title,
                "published_at": published_at,
                "status": status,
                "suspicious_count": suspicious,
            }
        )
    return items


def _video_detail(root: Path, video_id: str) -> dict[str, Any]:
    out_dir = quality_dir(root, video_id)
    raw_file = "raw.jsonl"
    meta_path = out_dir / "raw.meta.json"
    if meta_path.exists():
        raw_file = json.loads(meta_path.read_text(encoding="utf-8")).get("raw_file") or raw_file
    raw_rows = read_jsonl(out_dir / raw_file)
    ai_rows = read_jsonl(out_dir / "ai_cleaned.jsonl")
    approved_rows = read_jsonl(out_dir / "approved.jsonl")
    changes = read_jsonl(out_dir / "change_log.jsonl")
    state = load_review_state(root, video_id)
    video_url = ""
    if meta_path.exists():
        video_url = json.loads(meta_path.read_text(encoding="utf-8")).get("video_url") or ""

    segments = []
    for index, raw in enumerate(raw_rows):
        ai = ai_rows[index] if index < len(ai_rows) else raw
        approved = approved_rows[index] if index < len(approved_rows) else ai
        seg_changes = [c for c in changes if c.get("segment_id") == raw.get("segment_id")]
        flagged_relisten = approved.get("needs_relisten", False) or any(
            c.get("needs_relisten") for c in seg_changes
        )
        segments.append(
            {
                "segment_id": raw.get("segment_id"),
                "start": raw.get("start"),
                "end": raw.get("end"),
                "raw_text": raw.get("text"),
                "ai_text": ai.get("text"),
                "approved_text": approved.get("text"),
                "needs_relisten": flagged_relisten,
                "human_edited": approved.get("human_edited", False),
                "changes": seg_changes,
                "video_url": video_url or ai.get("video_url"),
            }
        )
    return {
        "video_id": video_id,
        "video_url": video_url,
        "local_video_url": _media_url(root, video_id, "video-light"),
        "local_audio_url": _media_url(root, video_id, "audio"),
        "review_state": state.to_dict() if state else None,
        "segments": segments,
        "history_files": list_history_files(root, video_id),
    }


REVIEW_HTML = """<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="utf-8"/>
  <title>Review transcript — Trại Cai Nghiện</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 1rem; max-width: 1400px; }
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 1px solid #ccc; padding: 0.4rem; vertical-align: top; }
    .diff-raw { background: #fff3f3; }
    .diff-ai { background: #f3f8ff; }
    .risk-low { color: green; }
    .risk-high { color: #b00; font-weight: bold; }
    #list { margin-bottom: 1.5rem; }
    button { margin-right: 0.3rem; margin-bottom: 0.25rem; }
    #player-panel { position: sticky; top: 0; z-index: 10; background: #fafafa; border: 1px solid #ccc;
      padding: 0.75rem; margin-bottom: 1rem; border-radius: 6px; }
    #player-panel video, #player-panel audio { width: 100%; max-height: 360px; }
    tr.segment-active { outline: 2px solid #06c; background: #f0f7ff; }
    tr.needs-relisten { background: #fff8e6; }
    .seg-actions button { font-size: 0.85rem; }
  </style>
</head>
<body>
  <h1>Review transcript (local)</h1>
  <p>Ba lớp: raw → AI đề xuất → approved. Chỉ sửa conservative; trading/số liệu cần nghe lại.</p>
  <div id="list"></div>
  <div id="detail"></div>
  <script>
    let currentVideoId = null;
    let currentDetail = null;
    let activeSegmentId = null;

    function encVideoId(videoId) {
      return encodeURIComponent(videoId);
    }

    function youtubeAt(url, seconds) {
      if (!url) return '#';
      const sep = url.includes('?') ? '&' : '?';
      return url + sep + 't=' + Math.max(0, Math.floor(seconds)) + 's';
    }

    async function api(path, opts) {
      const r = await fetch(path, opts);
      if (!r.ok) {
        const msg = await r.text();
        throw new Error(msg || ('HTTP ' + r.status));
      }
      return r.json();
    }

    /** Âm thanh: file audio (.m4a). Hình: video-light thường không có tiếng. */
    function getAudioPlayer() {
      return document.getElementById('media-player');
    }

    function getVideoPreview() {
      return document.getElementById('media-video');
    }

    function getPlayer() {
      return getAudioPlayer() || getVideoPreview();
    }

    function syncVideoToMaster() {
      const audio = getAudioPlayer();
      const video = getVideoPreview();
      if (audio && video) {
        video.currentTime = audio.currentTime;
      }
    }

    function segmentDomId(segmentId) {
      return 'seg-' + String(segmentId).replace(/[^a-zA-Z0-9._-]/g, '_');
    }

    function playSegment(start, end, segmentId) {
      const el = getPlayer();
      if (!el) {
        alert('Không có file video/audio local cho video này. Dùng link YouTube bên dưới.');
        return;
      }
      const from = Math.max(0, Number(start) || 0);
      const to = end != null ? Number(end) : null;
      el.currentTime = from;
      const video = getVideoPreview();
      if (video && video !== el) {
        video.currentTime = from;
      }
      el.play().catch(() => {});
      if (video && video !== el) {
        video.play().catch(() => {});
      }
      const domId = segmentDomId(segmentId);
      if (activeSegmentId) {
        const prev = document.getElementById(segmentDomId(activeSegmentId));
        if (prev) prev.classList.remove('segment-active');
      }
      activeSegmentId = segmentId;
      const row = document.getElementById(domId);
      if (row) {
        row.classList.add('segment-active');
        row.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      }
      if (el._stopAtHandler) {
        el.removeEventListener('timeupdate', el._stopAtHandler);
        el._stopAtHandler = null;
      }
      if (to != null && to > from) {
        const handler = () => {
          if (el.currentTime >= to) {
            el.pause();
            const vp = getVideoPreview();
            if (vp && vp !== el) vp.pause();
            el.removeEventListener('timeupdate', handler);
            el._stopAtHandler = null;
          }
        };
        el._stopAtHandler = handler;
        el.addEventListener('timeupdate', handler);
      }
      if (getAudioPlayer() && getVideoPreview()) {
        getAudioPlayer().addEventListener('timeupdate', syncVideoToMaster);
      }
    }

    function wirePlayerSync() {
      const audio = getAudioPlayer();
      const video = getVideoPreview();
      if (!audio || !video) return;
      audio.addEventListener('play', () => { video.currentTime = audio.currentTime; video.play().catch(() => {}); });
      audio.addEventListener('pause', () => video.pause());
      audio.addEventListener('seeked', syncVideoToMaster);
      audio.addEventListener('timeupdate', syncVideoToMaster);
    }

    function buildPlayerPanel(d) {
      const vSrc = d.local_video_url;
      const aSrc = d.local_audio_url;
      if (!vSrc && !aSrc) {
        return `<div id="player-panel"><p><strong>Chưa có media local.</strong>
          Chạy <code>cnga fetch-audio</code> (tiếng) và/hoặc <code>fetch-video-light</code> (hình).
          <a href="${escapeHtml(d.video_url||'')}" target="_blank">Mở YouTube</a></p></div>`;
      }
      let inner = '';
      if (aSrc && vSrc) {
        inner = `<p><strong>Tiếng:</strong> file audio · <strong>Hình:</strong> video-light (không có track tiếng trong MP4).
          <a href="${escapeHtml(d.video_url||'')}" target="_blank">YouTube</a></p>
          <video id="media-video" muted playsinline preload="metadata" src="${escapeHtml(vSrc)}"></video>
          <audio id="media-player" controls preload="metadata" src="${escapeHtml(aSrc)}"></audio>`;
      } else if (aSrc) {
        inner = `<p><strong>Chỉ audio local.</strong>
          <a href="${escapeHtml(d.video_url||'')}" target="_blank">YouTube</a></p>
          <audio id="media-player" controls preload="metadata" src="${escapeHtml(aSrc)}"></audio>`;
      } else {
        inner = `<p><strong>Chỉ video-light (thường không có tiếng).</strong>
          Chạy <code>cnga fetch-audio</code> để nghe trong dự án.
          <a href="${escapeHtml(d.video_url||'')}" target="_blank">YouTube</a></p>
          <video id="media-player" controls preload="metadata" src="${escapeHtml(vSrc)}"></video>`;
      }
      return `<div id="player-panel">${inner}
        <p style="margin:0.4rem 0 0;font-size:0.9rem;color:#444;">Dùng thanh điều khiển <strong>audio</strong> (nếu có) khi nghe theo đoạn transcript.</p>
      </div>`;
    }

    async function loadList() {
      const videos = await api('/api/videos');
      const el = document.getElementById('list');
      el.innerHTML = '<h2>Video (cũ → mới)</h2><table><tr><th>ID</th><th>Tiêu đề</th><th>Ngày</th><th>Trạng thái</th><th>Nghi ngờ</th></tr>' +
        videos.map(v => `<tr><td><a href="#" data-vid="${escapeHtml(v.video_id)}" class="vid-link">${escapeHtml(v.video_id)}</a></td>
          <td>${escapeHtml(v.title||'')}</td><td>${escapeHtml(v.published_at||'')}</td><td>${escapeHtml(v.status)}</td><td>${v.suspicious_count||0}</td></tr>`).join('') + '</table>';
      el.querySelectorAll('.vid-link').forEach(a => {
        a.addEventListener('click', e => { e.preventDefault(); loadDetail(a.dataset.vid); });
      });
    }

    async function loadDetail(videoId) {
      currentVideoId = videoId;
      const d = await api('/api/video/' + encVideoId(videoId));
      currentDetail = d;
      activeSegmentId = null;
      let html = `<h2>${escapeHtml(d.video_id)}</h2>`;
      html += buildPlayerPanel(d);
      html += `<p>
        <button type="button" id="btn-accept-low">Chấp nhận mọi thay đổi low-risk</button>
        <button type="button" id="btn-approve">Đánh dấu đã duyệt toàn video</button>
        <label style="margin-left:0.5rem"><input type="checkbox" id="filter-suspicious"/> Chỉ đoạn cần nghe lại / nghi ngờ</label>
      </p>`;
      html += '<table><tr><th>Time</th><th>Raw</th><th>AI</th><th>Approved</th><th>Thay đổi</th><th>Hành động</th></tr><tbody id="seg-body"></tbody></table>';
      document.getElementById('detail').innerHTML = html;
      document.getElementById('btn-accept-low').onclick = () => act(videoId, 'accept_all_low_risk', {});
      document.getElementById('btn-approve').onclick = () => act(videoId, 'approve', {});
      document.getElementById('filter-suspicious').onchange = () => renderSegments(d);
      wirePlayerSync();
      renderSegments(d);
    }

    function renderSegments(d) {
      const onlySusp = document.getElementById('filter-suspicious')?.checked;
      const body = document.getElementById('seg-body');
      if (!body) return;
      const rows = (d.segments || []).filter(s => {
        if (!onlySusp) return true;
        const risky = s.needs_relisten || (s.changes||[]).some(c => c.confidence === 'low' || c.needs_relisten);
        return risky;
      });
      body.innerHTML = rows.map(s => {
        const segId = s.segment_id;
        const yt = youtubeAt(s.video_url || d.video_url, s.start);
        const changes = (s.changes||[]).map(c =>
          `<div class="${c.confidence==='low'?'risk-high':'risk-low'}">${escapeHtml(c.change_type)}: ${escapeHtml(c.reason)} (${escapeHtml(c.confidence)})</div>`).join('');
        const relistenCls = s.needs_relisten ? 'needs-relisten' : '';
        return `<tr id="${segmentDomId(segId)}" class="${relistenCls}" data-segment-id="${escapeHtml(segId)}"
            data-start="${s.start}" data-end="${s.end}">
          <td>
            <button type="button" class="btn-play-seg">${Number(s.start).toFixed(1)}s</button>
            <a href="${escapeHtml(yt)}" target="_blank" title="YouTube tại timestamp">YT</a>
          </td>
          <td class="diff-raw">${escapeHtml(s.raw_text)}</td>
          <td class="diff-ai">${escapeHtml(s.ai_text)}</td>
          <td><textarea class="ap-text" rows="2" style="width:100%">${escapeHtml(s.approved_text)}</textarea></td>
          <td>${changes}</td>
          <td class="seg-actions">
            <button type="button" class="btn-listen">Nghe/xem đoạn</button>
            <button type="button" class="btn-accept">Accept AI</button>
            <button type="button" class="btn-reject">Reject</button>
            <button type="button" class="btn-save">Lưu sửa tay</button>
            <button type="button" class="btn-relisten">Cần nghe lại</button>
          </td></tr>`;
      }).join('');

      body.querySelectorAll('tr').forEach(tr => {
        const segId = tr.dataset.segmentId;
        const start = parseFloat(tr.dataset.start);
        const end = parseFloat(tr.dataset.end);
        tr.querySelector('.btn-play-seg')?.addEventListener('click', () => playSegment(start, end, segId));
        tr.querySelector('.btn-listen')?.addEventListener('click', () => playSegment(start, end, segId));
        tr.querySelector('.btn-accept')?.addEventListener('click', () => {
          const seg = (d.segments || []).find(x => x.segment_id === segId);
          act(d.video_id, 'accept_change', {
            segment_id: segId,
            ai_text: seg ? seg.ai_text : '',
          });
        });
        tr.querySelector('.btn-reject')?.addEventListener('click', () => {
          const seg = (d.segments || []).find(x => x.segment_id === segId);
          act(d.video_id, 'reject_change', {
            segment_id: segId,
            raw_text: seg ? seg.raw_text : '',
          });
        });
        tr.querySelector('.btn-save')?.addEventListener('click', () => {
          const text = tr.querySelector('.ap-text').value;
          act(d.video_id, 'edit_segment', { segment_id: segId, text });
        });
        tr.querySelector('.btn-relisten')?.addEventListener('click', async () => {
          await act(d.video_id, 'mark_needs_relisten', { segment_id: segId });
          playSegment(start, end, segId);
        });
      });
    }

    function escapeHtml(t) {
      return String(t ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }

    async function act(videoId, action, payload) {
      try {
        await api('/api/video/' + encVideoId(videoId) + '/action', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ action, ...payload })
        });
        await loadDetail(videoId);
        await loadList();
      } catch (err) {
        alert('Lỗi: ' + err.message);
      }
    }

    loadList();
  </script>
</body>
</html>
"""


class ReviewHandler(BaseHTTPRequestHandler):
    project_root: Path

    def _send_json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def _parse_video_id_from_api_path(self, path: str) -> str:
        rest = path.split("/api/video/", 1)[-1].strip("/")
        if rest.endswith("/action"):
            rest = rest[: -len("/action")]
        return urllib.parse.unquote(rest)

    def _serve_media(self, rel_path: str) -> None:
        config = load_project_config(self.project_root)
        decoded = urllib.parse.unquote(rel_path.replace("\\", "/"))
        target = (self.project_root / decoded).resolve()
        raw_root = (self.project_root / config["storage"]["raw_dir"]).resolve()
        if raw_root not in target.parents and target != raw_root:
            self.send_error(403)
            return
        if not target.is_file():
            self.send_error(404)
            return
        mime, _ = mimetypes.guess_type(str(target))
        content_type = mime or "application/octet-stream"
        file_size = target.stat().st_size
        range_header = self.headers.get("Range")
        if range_header:
            # bytes=0-1023
            units, _, range_spec = range_header.partition("=")
            if units.strip().lower() != "bytes":
                self.send_error(416)
                return
            start_s, _, end_s = range_spec.partition("-")
            start = int(start_s) if start_s else 0
            end = int(end_s) if end_s else file_size - 1
            end = min(end, file_size - 1)
            if start > end or start < 0:
                self.send_error(416)
                return
            length = end - start + 1
            self.send_response(206)
            self.send_header("Content-Type", content_type)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
            self.send_header("Content-Length", str(length))
            self.end_headers()
            with target.open("rb") as handle:
                handle.seek(start)
                self.wfile.write(handle.read(length))
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(file_size))
        self.end_headers()
        with target.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                self.wfile.write(chunk)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/" or parsed.path == "/index.html":
            self._send_html(REVIEW_HTML)
            return
        if parsed.path == "/api/videos":
            self._send_json(_video_list_payload(self.project_root))
            return
        if parsed.path.startswith("/api/video/") and "/action" not in parsed.path:
            video_id = self._parse_video_id_from_api_path(parsed.path)
            self._send_json(_video_detail(self.project_root, video_id))
            return
        if parsed.path.startswith("/media/"):
            self._serve_media(parsed.path[len("/media/") :])
            return
        self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if "/action" not in parsed.path:
            self.send_error(404)
            return
        video_id = self._parse_video_id_from_api_path(parsed.path)
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length).decode("utf-8"))
        action = str(body.get("action") or "")
        state = apply_review_action(self.project_root, video_id, action, body)
        self._send_json({"ok": True, "review_state": state.to_dict()})


def serve_review_ui(root: str | Path | None = None, host: str = "127.0.0.1", port: int = 8765) -> None:
    root_path = resolve_project_root(root)
    configure_local_environment(root_path)
    ReviewHandler.project_root = root_path
    server = ThreadingHTTPServer((host, port), ReviewHandler)
    print(f"Review UI: http://{host}:{port}/  (project: {root_path})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopped.")
