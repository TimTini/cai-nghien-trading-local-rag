"""YouTube collection pipeline.

Only metadata/subtitle sidecars are fetched by default. Audio/video downloads
must be an explicit future action because they can be large and may have legal
constraints.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

from .config import load_project_config
from .paths import configure_local_environment, to_project_relative
from .storage import sha256_file, write_jsonl, write_jsonl_once


def _import_ytdlp():
    try:
        import yt_dlp  # type: ignore
    except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("Missing optional dependency. Install with: python -m pip install -e .[youtube]") from exc
    return yt_dlp


def _timestamp() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _parse_upload_date(value: Any) -> str:
    if not value:
        return ""
    text = str(value)
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return text[:10]


def classify_content_type(entry: dict[str, Any]) -> str:
    """Separate regular videos, Shorts and livestream-like content."""

    url = str(entry.get("url") or entry.get("webpage_url") or "")
    duration = entry.get("duration")
    live_status = str(entry.get("live_status") or "")
    title = str(entry.get("title") or "").lower()

    if "shorts/" in url or (isinstance(duration, (int, float)) and duration <= 60):
        return "short"
    if live_status in {"is_live", "was_live", "post_live"} or "live" in title or "livestream" in title:
        return "livestream"
    return "regular"


def normalize_catalog_entry(entry: dict[str, Any]) -> dict[str, Any]:
    video_id = str(entry.get("id") or entry.get("video_id") or "")
    webpage_url = entry.get("webpage_url") or entry.get("url") or f"https://www.youtube.com/watch?v={video_id}"
    if video_id and "youtube.com" not in str(webpage_url):
        webpage_url = f"https://www.youtube.com/watch?v={video_id}"

    return {
        "video_id": video_id,
        "title": entry.get("title") or "",
        "description": entry.get("description") or "",
        "published_at": _parse_upload_date(entry.get("upload_date") or entry.get("release_date")),
        "duration": entry.get("duration"),
        "url": webpage_url,
        "thumbnail": entry.get("thumbnail") or "",
        "content_type": classify_content_type(entry),
        "raw_live_status": entry.get("live_status") or "",
    }


def collect_channel_catalog(root: str | Path | None = None, channel_url: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
    """Collect a channel catalog snapshot and write it as immutable raw data."""

    root_path = Path(root or ".").resolve()
    configure_local_environment(root_path)
    config = load_project_config(root_path)
    yt_dlp = _import_ytdlp()

    url = channel_url or config["channel"]["url"]
    if config["channel"].get("default_tab") and not url.rstrip("/").endswith(config["channel"]["default_tab"]):
        url = f"{url.rstrip('/')}/{config['channel']['default_tab']}"

    raw_dir = root_path / config["storage"]["raw_dir"]
    analysis_dir = root_path / config["storage"]["analysis_dir"]
    cache_dir = root_path / config["storage"]["cache_dir"] / "yt-dlp"
    options = {
        "extract_flat": "in_playlist",
        "ignoreerrors": True,
        "quiet": False,
        "skip_download": True,
        "cachedir": str(cache_dir),
        "paths": {"home": str(raw_dir)},
    }
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=False)

    entries = [normalize_catalog_entry(item) for item in (info or {}).get("entries", []) if item]
    entries = [item for item in entries if item["video_id"]]
    entries.sort(key=lambda item: (item.get("published_at") or "9999-99-99", item["video_id"]))
    if limit:
        entries = entries[:limit]

    stamp = _timestamp()
    snapshot_path = raw_dir / "catalog" / f"catalog-{stamp}.jsonl"
    write_jsonl_once(snapshot_path, entries, root_path)
    write_jsonl(analysis_dir / "state" / "latest_catalog.jsonl", entries, root_path)
    return entries


def fetch_video_sidecars(root: str | Path | None, entry: dict[str, Any]) -> dict[str, Any]:
    """Fetch info-json, thumbnails and subtitles for one video without media."""

    root_path = Path(root or ".").resolve()
    configure_local_environment(root_path)
    config = load_project_config(root_path)
    yt_dlp = _import_ytdlp()

    raw_dir = root_path / config["storage"]["raw_dir"]
    cache_dir = root_path / config["storage"]["cache_dir"] / "yt-dlp"
    video_id = entry["video_id"]
    video_dir = raw_dir / "videos" / video_id
    manifest_path = video_dir / "manifest.json"
    if manifest_path.exists():
        return json.loads(manifest_path.read_text(encoding="utf-8"))

    video_dir.mkdir(parents=True, exist_ok=True)
    options = {
        "skip_download": True,
        "writeinfojson": True,
        "writethumbnail": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["vi", "vi.*", "en", "en.*"],
        "ignoreerrors": True,
        "overwrites": False,
        "cachedir": str(cache_dir),
        "paths": {"home": str(video_dir)},
        "outtmpl": {"default": str(video_dir / "%(id)s.%(ext)s")},
    }
    with yt_dlp.YoutubeDL(options) as ydl:
        ydl.download([entry["url"]])

    files = []
    for path in sorted(video_dir.iterdir()):
        if path == manifest_path or path.is_dir():
            continue
        files.append({"path": to_project_relative(path, root_path), "sha256": sha256_file(path)})

    manifest = {
        "video_id": video_id,
        "title": entry.get("title", ""),
        "published_at": entry.get("published_at", ""),
        "url": entry.get("url", ""),
        "content_type": entry.get("content_type", ""),
        "collected_at": _timestamp(),
        "files": files,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return manifest


def collect(root: str | Path | None = None, limit: int | None = None, fetch_sidecars: bool = False) -> list[dict[str, Any]]:
    entries = collect_channel_catalog(root=root, limit=limit)
    if fetch_sidecars:
        for entry in entries:
            fetch_video_sidecars(root, entry)
    return entries

