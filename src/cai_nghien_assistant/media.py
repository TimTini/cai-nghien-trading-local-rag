"""Download audio-only and light video tracks for ASR and visual analysis."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import load_project_config
from .paths import configure_local_environment, to_project_relative
from .storage import atomic_write_json, sha256_file
from .youtube_collect import catalog_entries_filtered, load_latest_catalog


def _catalog_entry(root: Path, video_id: str) -> dict[str, Any] | None:
    for entry in load_latest_catalog(root):
        if entry.get("video_id") == video_id:
            return entry
    return None


def select_catalog_entries(
    root: str | Path | None = None,
    limit: int | None = None,
    content_type: str | None = None,
    offset: int = 0,
    published_year: int | None = None,
    video_id: str | None = None,
) -> list[dict[str, Any]]:
    root_path = Path(root or ".").resolve()
    if video_id:
        entry = _catalog_entry(root_path, video_id)
        return [entry] if entry else []
    entries = catalog_entries_filtered(root_path, content_type=content_type, published_year=published_year)
    if content_type and content_type not in {"regular+livestream", "all"}:
        entries = [entry for entry in entries if entry.get("content_type") == content_type]
    if offset:
        entries = entries[offset:]
    return entries[:limit] if limit else entries


def _import_ytdlp():
    try:
        import yt_dlp  # type: ignore
    except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("Missing yt-dlp. Install with: uv sync --extra youtube") from exc
    return yt_dlp


def _manifest_valid(manifest_path: Path, root: Path) -> bool:
    if not manifest_path.exists():
        return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    for file_info in manifest.get("files", []):
        file_path = root / file_info.get("path", "")
        if file_path.exists() and file_path.is_file() and file_path.stat().st_size > 0:
            return True
    return False


def _media_files(media_dir: Path, manifest_path: Path, root_path: Path) -> list[dict[str, Any]]:
    files = []
    ignored_suffixes = {".part", ".ytdl", ".temp", ".tmp"}
    for path in sorted(media_dir.iterdir()):
        if path == manifest_path or path.is_dir() or path.suffix.lower() in ignored_suffixes:
            continue
        if path.stat().st_size <= 0:
            continue
        files.append(
            {
                "path": to_project_relative(path, root_path),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
        )
    return files


def _fallback_selectors(media_kind: str, format_selector: str) -> list[str]:
    selectors = [format_selector]
    if media_kind == "audio":
        selectors.extend(
            [
                "bestaudio[ext=webm]/bestaudio/best[height<=720][ext=mp4]/best[height<=480][ext=mp4]/best",
                "bestaudio/best",
            ]
        )
    if media_kind == "video-light":
        selectors.extend(
            [
                "18/best[height<=720][ext=mp4]/best[height<=480][ext=mp4]/best[height<=720]/best",
                "best[height<=720]/best",
            ]
        )
    return list(dict.fromkeys(selectors))


def download_media_track(
    root: str | Path | None,
    entry: dict[str, Any],
    media_kind: str,
    format_selector: str,
    force: bool = False,
) -> dict[str, Any]:
    """Download one media track into data/raw/videos/<id>/<media_kind>."""

    root_path = Path(root or ".").resolve()
    configure_local_environment(root_path)
    config = load_project_config(root_path)
    yt_dlp = _import_ytdlp()

    video_id = entry["video_id"]
    media_dir = root_path / config["storage"]["raw_dir"] / "videos" / video_id / media_kind
    manifest_path = media_dir / "manifest.json"
    if not force and _manifest_valid(manifest_path, root_path):
        return json.loads(manifest_path.read_text(encoding="utf-8"))

    media_dir.mkdir(parents=True, exist_ok=True)
    attempted_selectors = []
    files: list[dict[str, Any]] = []
    selected_format = format_selector
    for selected_format in _fallback_selectors(media_kind, format_selector):
        attempted_selectors.append(selected_format)
        options = {
            "format": selected_format,
            "ignoreerrors": True,
            "quiet": False,
            "continuedl": True,
            "retries": 5,
            "fragment_retries": 5,
            "skip_download": False,
            "overwrites": False,
            "writeinfojson": False,
            "writethumbnail": False,
            "writesubtitles": False,
            "writeautomaticsub": False,
            "cachedir": str(root_path / config["storage"]["cache_dir"] / "yt-dlp"),
            "paths": {"home": str(media_dir)},
            "outtmpl": {"default": str(media_dir / "%(id)s.%(ext)s")},
        }
        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.download([entry["url"]])
        files = _media_files(media_dir, manifest_path, root_path)
        if files:
            break
        print(f"[{media_kind}] no media file for selector={selected_format!r}; trying fallback")

    manifest = {
        "video_id": video_id,
        "title": entry.get("title", ""),
        "published_at": entry.get("published_at", ""),
        "url": entry.get("url", ""),
        "content_type": entry.get("content_type", ""),
        "media_kind": media_kind,
        "format_selector": selected_format,
        "attempted_selectors": attempted_selectors,
        "files": files,
    }
    atomic_write_json(manifest_path, manifest, root_path)
    return manifest


def fetch_audio_batch(
    root: str | Path | None = None,
    limit: int | None = None,
    content_type: str | None = None,
    offset: int = 0,
    force: bool = False,
    published_year: int | None = None,
    video_id: str | None = None,
) -> list[dict[str, Any]]:
    root_path = Path(root or ".").resolve()
    config = load_project_config(root_path)
    entries = select_catalog_entries(
        root_path,
        limit=limit,
        content_type=content_type,
        offset=offset,
        published_year=published_year,
        video_id=video_id,
    )
    manifests = []
    for index, entry in enumerate(entries, start=1):
        print(f"[audio] {index}/{len(entries)} {entry.get('published_at') or 'unknown'} {entry['video_id']} {entry.get('title', '')}")
        manifests.append(download_media_track(root_path, entry, "audio", config["media"]["audio_format"], force=force))
    return manifests


def fetch_video_light_batch(
    root: str | Path | None = None,
    limit: int | None = None,
    content_type: str | None = None,
    offset: int = 0,
    force: bool = False,
    published_year: int | None = None,
    video_id: str | None = None,
) -> list[dict[str, Any]]:
    root_path = Path(root or ".").resolve()
    config = load_project_config(root_path)
    entries = select_catalog_entries(
        root_path,
        limit=limit,
        content_type=content_type,
        offset=offset,
        published_year=published_year,
        video_id=video_id,
    )
    manifests = []
    for index, entry in enumerate(entries, start=1):
        print(f"[video-light] {index}/{len(entries)} {entry.get('published_at') or 'unknown'} {entry['video_id']} {entry.get('title', '')}")
        manifests.append(download_media_track(root_path, entry, "video-light", config["media"]["video_light_format"], force=force))
    return manifests


def first_media_file(root: str | Path | None, video_id: str, media_kind: str) -> Path | None:
    root_path = Path(root or ".").resolve()
    config = load_project_config(root_path)
    manifest_path = root_path / config["storage"]["raw_dir"] / "videos" / video_id / media_kind / "manifest.json"
    if not manifest_path.exists():
        return None
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for file_info in manifest.get("files", []):
        path = root_path / file_info.get("path", "")
        if path.exists() and path.is_file():
            return path
    return None
