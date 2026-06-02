"""Storage helpers for immutable raw data and regenerable analysis data."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable

from .paths import assert_inside_project, resolve_project_root


class RawDataExistsError(RuntimeError):
    """Raised when code attempts to mutate an immutable raw artifact."""


def canonical_json_bytes(data: Any) -> bytes:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json_once(path: str | Path, data: Any, root: str | Path | None = None) -> None:
    """Write raw JSON only once. Rewriting different bytes is forbidden."""

    root_path = resolve_project_root(root)
    target = assert_inside_project(path, root_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical_json_bytes(data)
    if target.exists():
        current = target.read_bytes()
        if current != payload:
            raise RawDataExistsError(f"Refuse to mutate raw artifact: {target}")
        return
    target.write_bytes(payload)


def write_text_once(path: str | Path, text: str, root: str | Path | None = None) -> None:
    root_path = resolve_project_root(root)
    target = assert_inside_project(path, root_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = text.encode("utf-8")
    if target.exists():
        current = target.read_bytes()
        if current != payload:
            raise RawDataExistsError(f"Refuse to mutate raw artifact: {target}")
        return
    target.write_bytes(payload)


def atomic_write_text(path: str | Path, text: str, root: str | Path | None = None) -> None:
    """Atomically write regenerable analysis text."""

    root_path = resolve_project_root(root)
    target = assert_inside_project(path, root_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=target.parent, delete=False) as handle:
        handle.write(text)
        tmp_name = handle.name
    os.replace(tmp_name, target)


def atomic_write_json(path: str | Path, data: Any, root: str | Path | None = None) -> None:
    atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), root)


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    if not Path(path).exists():
        return []
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: str | Path, rows: Iterable[dict[str, Any]], root: str | Path | None = None) -> None:
    text = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)
    atomic_write_text(path, text, root)


def write_jsonl_once(path: str | Path, rows: Iterable[dict[str, Any]], root: str | Path | None = None) -> None:
    text = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)
    write_text_once(path, text, root)

