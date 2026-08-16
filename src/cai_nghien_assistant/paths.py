"""Project-local path and environment helpers.

The project must be movable. For that reason, runtime paths are resolved from a
project root and saved as relative paths whenever they are persisted.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable


PROJECT_MARKERS = ("config/project.toml", "pyproject.toml")
NON_PATH_ENV_KEYS = {
    "UV_LINK_MODE",
    "PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK",
    "FLAGS_use_mkldnn",
    "FLAGS_use_onednn",
    "PADDLE_DISABLE_MKLDNN",
    "ONEDNN_VERBOSE",
}


def find_project_root(start: str | Path | None = None) -> Path:
    """Find the nearest project root from *start* or the current directory."""

    current = Path(start or os.environ.get("CNGA_PROJECT_ROOT") or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent

    for candidate in (current, *current.parents):
        if all((candidate / marker).exists() for marker in PROJECT_MARKERS):
            return candidate

    return current


def resolve_project_root(root: str | Path | None = None) -> Path:
    """Resolve a user supplied root without storing absolute paths in config."""

    if root is None:
        return find_project_root()
    return Path(root).resolve()


def project_path(*parts: str | Path, root: str | Path | None = None) -> Path:
    """Return an absolute path inside the project."""

    return resolve_project_root(root).joinpath(*map(str, parts)).resolve()


def assert_inside_project(path: str | Path, root: str | Path | None = None) -> Path:
    """Validate that *path* stays inside *root*."""

    root_path = resolve_project_root(root)
    target = Path(path).resolve()
    if target == root_path or root_path in target.parents:
        return target
    raise ValueError(f"Path escapes project root: {target}")


def to_project_relative(path: str | Path, root: str | Path | None = None) -> str:
    """Convert an absolute project path to a portable POSIX-style relative path."""

    root_path = resolve_project_root(root)
    target = assert_inside_project(path, root_path)
    return target.relative_to(root_path).as_posix()


def ensure_project_tree(root: str | Path | None = None) -> None:
    """Create the local runtime tree used by the pipeline."""

    root_path = resolve_project_root(root)
    directories: Iterable[str] = (
        "data/raw/catalog",
        "data/raw/videos",
        "data/analysis/state",
        "data/analysis/transcripts",
        "data/analysis/transcript_quality",
        "data/analysis/transcript_quality/history",
        "data/analysis/frames",
        "data/analysis/ocr",
        "data/analysis/extractions/content",
        "data/analysis/extractions/style",
        "data/analysis/knowledge",
        "data/analysis/knowledge/videos",
        "data/analysis/knowledge/playbook",
        "data/analysis/index",
        "data/analysis/cache",
        "logs",
        ".cache/yt-dlp",
        ".cache/huggingface",
        ".cache/torch",
        ".cache/paddleocr",
        ".cache/paddlex",
        ".cache/matplotlib",
        ".cache/numba",
        "models/chat",
        "models/vision",
        "models/embeddings",
        "models/asr",
        "models/ocr",
        "models/ollama",
    )
    for directory in directories:
        assert_inside_project(root_path / directory, root_path).mkdir(parents=True, exist_ok=True)


def configure_local_environment(root: str | Path | None = None) -> dict[str, str]:
    """Force common ML/download caches to live under the project.

    This function intentionally overwrites process environment variables before
    optional heavy libraries are imported.
    """

    root_path = resolve_project_root(root)
    ensure_project_tree(root_path)

    env_paths = {
        "CNGA_PROJECT_ROOT": root_path,
        "XDG_CACHE_HOME": root_path / ".cache",
        "HF_HOME": root_path / ".cache" / "huggingface",
        "HUGGINGFACE_HUB_CACHE": root_path / ".cache" / "huggingface" / "hub",
        "TRANSFORMERS_CACHE": root_path / ".cache" / "huggingface" / "transformers",
        "SENTENCE_TRANSFORMERS_HOME": root_path / "models" / "embeddings",
        "TORCH_HOME": root_path / ".cache" / "torch",
        "PADDLEOCR_HOME": root_path / ".cache" / "paddleocr",
        "PADDLE_PDX_CACHE_HOME": root_path / "models" / "ocr" / "paddlex",
        "PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK": "True",
        "FLAGS_use_mkldnn": "0",
        "FLAGS_use_onednn": "0",
        "PADDLE_DISABLE_MKLDNN": "1",
        "ONEDNN_VERBOSE": "0",
        "MPLCONFIGDIR": root_path / ".cache" / "matplotlib",
        "NUMBA_CACHE_DIR": root_path / ".cache" / "numba",
        "YTDLP_CACHE_DIR": root_path / ".cache" / "yt-dlp",
        "UV_CACHE_DIR": root_path / ".cache" / "uv",
        "PIP_CACHE_DIR": root_path / ".cache" / "pip",
        "UV_LINK_MODE": "copy",
        "OLLAMA_MODELS": root_path / "models" / "ollama",
    }

    exported: dict[str, str] = {}
    for key, value in env_paths.items():
        if key in NON_PATH_ENV_KEYS:
            os.environ[key] = str(value)
            exported[key] = str(value)
            continue
        target = assert_inside_project(value, root_path) if key != "CNGA_PROJECT_ROOT" else root_path
        os.environ[key] = str(target)
        exported[key] = str(target)
    return exported
