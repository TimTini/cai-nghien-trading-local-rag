"""Download the repo-local GGUF model used by scripts/local_console_chat.py.

This does not use Ollama Desktop or the Ollama model store. The model is stored
under the current project (default: models/chat/...).

Usage:
  rtk uv run --extra chat python scripts/download_local_chat_model.py --root H:\\cai-nghien-trading-local-rag
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any
from urllib.parse import quote


DEFAULT_CONFIG = Path("config/local_chat_model.toml")


def configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="replace")


def load_config(root: Path, config_path: Path) -> dict[str, Any]:
    full_path = config_path if config_path.is_absolute() else root / config_path
    if not full_path.exists():
        raise FileNotFoundError(f"Missing config: {full_path}")
    with full_path.open("rb") as handle:
        return tomllib.load(handle)


def project_path(root: Path, relative_path: str) -> Path:
    candidate = (root / relative_path).resolve()
    root_resolved = root.resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(f"Path escapes project root: {candidate}") from exc
    return candidate


def resolve_url(repo_id: str, filename: str) -> str:
    return f"https://huggingface.co/{repo_id}/resolve/main/{quote(filename)}"


def download_with_curl(url: str, target_path: Path, force: bool) -> bool:
    curl = shutil.which("curl.exe") or shutil.which("curl")
    if not curl:
        return False
    if force and target_path.exists():
        target_path.unlink()
    command = [
        curl,
        "-L",
        "--fail",
        "--continue-at",
        "-",
        "--output",
        str(target_path),
        url,
    ]
    print("Using curl downloader (resumable).", flush=True)
    subprocess.run(command, check=True)
    return True


def download_with_huggingface_hub(repo_id: str, filename: str, target_dir: Path, force: bool) -> Path:
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency: huggingface_hub. Install with: rtk uv sync --extra chat"
        ) from exc

    downloaded = hf_hub_download(
        repo_id=repo_id,
        filename=filename,
        local_dir=str(target_dir),
        force_download=force,
    )
    return Path(downloaded).resolve()


def main() -> int:
    configure_stdio()
    parser = argparse.ArgumentParser(description="Download local GGUF chat model into this project.")
    parser.add_argument("--root", type=Path, default=Path("."), help="Project root.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="Model config TOML.")
    parser.add_argument("--repo-id", default=None, help="Override Hugging Face repo id.")
    parser.add_argument("--filename", default=None, help="Override GGUF filename.")
    parser.add_argument("--force", action="store_true", help="Re-download even if file exists.")
    parser.add_argument(
        "--method",
        choices=["auto", "curl", "hf"],
        default="auto",
        help="Download backend. auto prefers curl for visible resumable progress.",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    config = load_config(root, args.config)
    model_cfg = config["model"]
    repo_id = args.repo_id or str(model_cfg["repo_id"])
    filename = args.filename or str(model_cfg["filename"])
    target_dir = project_path(root, str(model_cfg["relative_dir"]))
    target_path = target_dir / filename

    if target_path.exists() and target_path.stat().st_size > 0 and not args.force:
        print(f"Model already exists: {target_path}")
        return 0

    target_dir.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {repo_id}/{filename}", flush=True)
    print(f"Target: {target_path}", flush=True)
    url = resolve_url(repo_id, filename)
    try:
        if args.method in {"auto", "curl"} and download_with_curl(url, target_path, args.force):
            downloaded = target_path.resolve()
        elif args.method == "curl":
            print("curl not found.", file=sys.stderr)
            return 2
        else:
            print("Using huggingface_hub downloader.", flush=True)
            downloaded = download_with_huggingface_hub(repo_id, filename, target_dir, args.force)
    except Exception as exc:
        print(f"Download failed: {exc}", file=sys.stderr)
        return 1

    print(f"Done: {downloaded}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
