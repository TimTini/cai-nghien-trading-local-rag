"""Download audio-only and light video tracks for ASR and visual analysis."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import load_project_config
from .paths import configure_local_environment, to_project_relative
from .storage import atomic_write_json, sha256_file
from .youtube_collect import load_latest_catalog


def _import_ytdlp():
    try:
        import yt_dlp  # type: ignore
    except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("Missing yt-dlp. Install with: uv sync --extra youtube") from exc
    return yt_dlp


def select_catalog_entries(
    root: str | Path | None = None,
    limit: int | None = None,
    content_type: str | None = None,
    offset: int = 0,
) -> list[dict[str, Any]]:
    entries = load_latest_catalog(root)
    if content_type:
        entries = [entry for entry in entries if entry.get("content_type") == content_type]
    if offset:
        entries = entries[offset:]
    return entries[:limit] if limit else entries


def _manifest_valid(manifest_path: Path, root: Path) -> bool:
    if not manifest_path.exists():
        return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    for file_info in manifest.get("files", []):
        file_path = root / file_info.get("path", "")
        if file_path.exists():
            return True
    return False


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
    before = {path.name for path in media_dir.iterdir() if path.is_file()}
    options = {
        "format": format_selector,
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

    files = []
    for path in sorted(media_dir.iterdir()):
        if path == manifest_path or path.is_dir():
            continue
        if path.name not in before or path.stat().st_size > 0:
            files.append(
                {
                    "path": to_project_relative(path, root_path),
                    "sha256": sha256_file(path),
                    "bytes": path.stat().st_size,
                }
            )
    manifest = {
        "video_id": video_id,
        "title": entry.get("title", ""),
        "published_at": entry.get("published_at", ""),
        "url": entry.get("url", ""),
        "content_type": entry.get("content_type", ""),
        "media_kind": media_kind,
        "format_selector": format_selector,
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
) -> list[dict[str, Any]]:
    root_path = Path(root or ".").resolve()
    config = load_project_config(root_path)
    entries = select_catalog_entries(root_path, limit=limit, content_type=content_type, offset=offset)
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
) -> list[dict[str, Any]]:
    root_path = Path(root or ".").resolve()
    config = load_project_config(root_path)
    entries = select_catalog_entries(root_path, limit=limit, content_type=content_type, offset=offset)
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

