"""Shared helpers for scripts/run_layer_*.py — paths relative to project root."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def resolve_root(root: str | Path | None) -> Path:
    return Path(root or os.environ.get("CNGA_PROJECT_ROOT") or ".").resolve()


def run_cnga(root: Path, *args: str, check: bool = True) -> int:
    command = [sys.executable, "-m", "cai_nghien_assistant.cli", "--root", str(root), *args]
    print("$ " + " ".join(command), flush=True)
    completed = subprocess.run(command, cwd=str(root), check=False)
    if check and completed.returncode != 0:
        raise SystemExit(completed.returncode)
    return int(completed.returncode)


def load_toml_section(root: Path, *keys: str) -> dict:
    try:
        from cai_nghien_assistant.config import load_project_config

        data = load_project_config(root)
        for key in keys:
            data = data.get(key) or {}
        return dict(data) if isinstance(data, dict) else {}
    except Exception:
        return {}


def content_type_arg(value: str) -> list[str]:
    """Empty config value => no --content-type (all catalog types with transcript)."""
    value = (value or "").strip()
    if not value or value == "all":
        return []
    return ["--content-type", value]
