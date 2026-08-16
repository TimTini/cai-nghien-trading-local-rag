"""Playbook directories under data/analysis/knowledge."""

from __future__ import annotations

from pathlib import Path

from ..config import load_project_config


def knowledge_root(root: Path) -> Path:
    config = load_project_config(root)
    playbook_cfg = config.get("playbook") or {}
    rel = str(playbook_cfg.get("output_dir") or "data/analysis/knowledge")
    return root / rel


def videos_root(root: Path) -> Path:
    return knowledge_root(root) / "videos"


def video_dir(root: Path, video_id: str) -> Path:
    return videos_root(root) / video_id


def playbook_dir(root: Path) -> Path:
    return knowledge_root(root) / "playbook"


def index_path(root: Path) -> Path:
    return playbook_dir(root) / "index.json"
