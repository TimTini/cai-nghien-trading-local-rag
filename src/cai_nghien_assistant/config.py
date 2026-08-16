"""Configuration loading with portable relative paths."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

from .paths import assert_inside_project, resolve_project_root


DEFAULT_CONFIG: dict[str, Any] = {
    "channel": {
        "url": "https://www.youtube.com/@cainghientrading",
        "default_tab": "videos",
    },
    "storage": {
        "raw_dir": "data/raw",
        "analysis_dir": "data/analysis",
        "logs_dir": "logs",
        "cache_dir": ".cache",
        "models_dir": "models",
    },
    "pipeline": {
        "version": "0.1.0",
        "default_batch_size": 8,
        "oldest_first": True,
    },
    "retrieval": {
        "index_path": "data/analysis/index/search.sqlite",
        "default_limit": 5,
        "min_content_evidence": 1,
    },
    "models": {
        "chat_model_dir": "models/chat",
        "vision_model_dir": "models/vision",
        "embedding_model_dir": "models/embeddings",
        "ollama_models_dir": "models/ollama",
    },
    "guardrails": {
        "unknown_answer": "Tôi không biết dựa trên dữ liệu đã phân tích từ kênh này.",
        "allow_cloud": False,
        "allow_style_as_fact": False,
    },
    "playbook": {
        "output_dir": "data/analysis/knowledge",
    },
}


def _merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge_dict(result[key], value)
        else:
            result[key] = value
    return result


def _validate_relative_paths(config: dict[str, Any], root: Path) -> None:
    path_sections = ("storage", "retrieval", "models")
    for section in path_sections:
        for key, value in config.get(section, {}).items():
            if not key.endswith(("_dir", "_path")):
                continue
            path = Path(str(value))
            if path.is_absolute():
                raise ValueError(f"Config path must be relative: [{section}] {key}={value!r}")
            assert_inside_project(root / path, root)


def load_project_config(root: str | Path | None = None) -> dict[str, Any]:
    root_path = resolve_project_root(root)
    config_path = root_path / "config" / "project.toml"
    config = copy.deepcopy(DEFAULT_CONFIG)
    if config_path.exists():
        with config_path.open("rb") as handle:
            config = _merge_dict(config, tomllib.load(handle))
    _validate_relative_paths(config, root_path)
    return config


def config_path(root: str | Path | None, dotted_key: str) -> Path:
    config = load_project_config(root)
    value: Any = config
    for part in dotted_key.split("."):
        value = value[part]
    path = Path(str(value))
    if path.is_absolute():
        raise ValueError(f"Config path must be relative: {dotted_key}")
    return assert_inside_project(resolve_project_root(root) / path, root)

