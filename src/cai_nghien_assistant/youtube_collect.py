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
from .storage import atomic_write_json, sha256_file, write_jsonl, write_jsonl_once


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


def _raw_metadata_snapshot(info: dict[str, Any]) -> dict[str, Any]:
    """Keep original metadata fields needed by the project without huge format lists."""

    wanted_keys = (
        "id",
        "title",
        "description",
        "upload_date",
        "release_date",
        "timestamp",
        "duration",
        "webpage_url",
        "thumbnail",
        "thumbnails",
        "subtitles",
        "automatic_captions",
        "live_status",
        "channel",
        "channel_id",
        "uploader",
        "uploader_id",
    )
    return {key: info.get(key) for key in wanted_keys if key in info}


def fetch_video_metadata(root: str | Path | None, entry: dict[str, Any], stamp: str | None = None) -> dict[str, Any]:
    """Fetch one video's full metadata and persist an immutable raw snapshot."""

    root_path = Path(root or ".").resolve()
    configure_local_environment(root_path)
    config = load_project_config(root_path)
    yt_dlp = _import_ytdlp()

    raw_dir = root_path / config["storage"]["raw_dir"]
    analysis_dir = root_path / config["storage"]["analysis_dir"]
    cache_dir = root_path / config["storage"]["cache_dir"] / "yt-dlp"
    video_id = entry["video_id"]
    latest_path = analysis_dir / "state" / "video_metadata" / f"{video_id}.json"
    if latest_path.exists():
        latest = json.loads(latest_path.read_text(encoding="utf-8"))
        if latest.get("published_at"):
            merged = {**entry, **latest}
            return merged

    options = {
        "ignoreerrors": True,
        "quiet": True,
        "skip_download": True,
        "cachedir": str(cache_dir),
        "paths": {"home": str(raw_dir / "videos" / video_id)},
    }
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(entry["url"], download=False) or {}

    normalized = normalize_catalog_entry({**entry, **info})
    snapshot = {
        "collected_at": stamp or _timestamp(),
        "normalized": normalized,
        "raw_metadata": _raw_metadata_snapshot(info),
    }
    metadata_dir = raw_dir / "videos" / video_id / "metadata"
    write_jsonl_once(metadata_dir / f"metadata-{snapshot['collected_at']}.jsonl", [snapshot], root_path)
    atomic_write_json(latest_path, normalized, root_path)
    return normalized


def enrich_catalog_entries(
    root: str | Path | None,
    entries: list[dict[str, Any]],
    force: bool = False,
) -> list[dict[str, Any]]:
    """Ensure catalog entries have upload dates before oldest-first processing."""

    stamp = _timestamp()
    enriched: list[dict[str, Any]] = []
    for index, entry in enumerate(entries, start=1):
        if force or not entry.get("published_at"):
            print(f"[metadata] {index}/{len(entries)} {entry['video_id']}")
            enriched.append(fetch_video_metadata(root, entry, stamp=stamp))
        else:
            enriched.append(entry)
    return enriched


def sort_oldest_first(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(entries, key=lambda item: (item.get("published_at") or "9999-99-99", item["video_id"]))


def load_latest_catalog(root: str | Path | None = None) -> list[dict[str, Any]]:
    root_path = Path(root or ".").resolve()
    config = load_project_config(root_path)
    catalog_path = root_path / config["storage"]["analysis_dir"] / "state" / "latest_catalog.jsonl"
    if not catalog_path.exists():
        return []
    entries = [json.loads(line) for line in catalog_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return sort_oldest_first(entries)


def collect_channel_catalog(
    root: str | Path | None = None,
    channel_url: str | None = None,
    limit: int | None = None,
    enrich_metadata: bool = True,
) -> list[dict[str, Any]]:
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
    if enrich_metadata:
        entries = enrich_catalog_entries(root_path, entries)
    entries = sort_oldest_first(entries)
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


def collect(
    root: str | Path | None = None,
    limit: int | None = None,
    fetch_sidecars: bool = False,
    sidecar_limit: int | None = None,
    enrich_metadata: bool = True,
) -> list[dict[str, Any]]:
    entries = collect_channel_catalog(root=root, limit=limit, enrich_metadata=enrich_metadata)
    if fetch_sidecars:
        selected = entries[:sidecar_limit] if sidecar_limit else entries
        for entry in selected:
            fetch_video_sidecars(root, entry)
    return entries


def fetch_oldest_sidecars(
    root: str | Path | None = None,
    limit: int | None = None,
    content_type: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch subtitle/info sidecars from the already dated catalog, oldest first."""

    root_path = Path(root or ".").resolve()
    entries = load_latest_catalog(root_path)
    if not entries:
        entries = collect_channel_catalog(root_path)
    if content_type:
        entries = [entry for entry in entries if entry.get("content_type") == content_type]
    selected = entries[:limit] if limit else entries
    manifests: list[dict[str, Any]] = []
    for index, entry in enumerate(selected, start=1):
        print(
            "[sidecars] "
            f"{index}/{len(selected)} {entry.get('published_at') or 'unknown-date'} "
            f"{entry['video_id']} {entry.get('title', '')}"
        )
        manifests.append(fetch_video_sidecars(root_path, entry))
    return manifests
