#!/usr/bin/env python3
"""Shared helpers for agent-direct raw-only transcript cleaning."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]


def dedupe_consecutive_phrases(text: str) -> str:
    words = text.split()
    if len(words) < 4:
        return text
    out: list[str] = []
    i = 0
    while i < len(words):
        max_try = min(40, (len(words) - i) // 2)
        matched = False
        for n in range(max_try, 0, -1):
            chunk = words[i : i + n]
            reps = 1
            j = i + n
            while j + n <= len(words) and words[j : j + n] == chunk:
                reps += 1
                j += n
            if reps > 1:
                i = i + n * reps
                out.extend(chunk)
                matched = True
                break
        if not matched:
            out.append(words[i])
            i += 1
    return " ".join(out)


def apply_rule_list(
    text: str,
    rules: list[tuple[str, str, str, str, str, bool, bool]],
) -> tuple[str, list[dict]]:
    fixes: list[dict] = []
    t = text
    for pattern, repl, ctype, reason, conf, trading, suspicious in rules:
        new_t, n = re.subn(pattern, repl, t, flags=re.I)
        if n > 0 and new_t != t:
            fixes.append(
                {
                    "change_type": ctype,
                    "confidence": conf,
                    "reason": reason,
                    "trading_term_flag": trading,
                    "needs_relisten": conf == "low" or suspicious,
                    "suspicious": suspicious,
                }
            )
            t = new_t

    t2 = dedupe_consecutive_phrases(t)
    if t2 != t:
        fixes.append(
            {
                "change_type": "asr_stutter",
                "confidence": "high",
                "reason": "ASR lặp cụm từ trong cùng segment",
                "trading_term_flag": False,
                "needs_relisten": False,
            }
        )
        t = t2
    return t, fixes


COMMON_RULES: list[tuple[str, str, str, str, str, bool, bool]] = [
    (r"\bOKEx\b", "OKX", "brand_fix", "ASR: OKEx → OKX", "high", True, False),
    (r"\bokex\b", "OKX", "brand_fix", "ASR: okex → OKX", "high", True, False),
    (r"\bfuture\b", "futures", "asr_term", "ASR: future → futures", "high", True, False),
    (r"\bsport\b", "spot", "asr_term", "ASR: sport → spot", "high", True, False),
    (r"\bboss\b", "bot", "asr_term", "ASR: boss → bot", "high", True, False),
    (r"\bbót\b", "bot", "asr_term", "ASR: bót → bot", "high", True, False),
]


def clean_video(
    video_id: str,
    extra_rules: list[tuple[str, str, str, str, str, bool, bool]] | None = None,
    segment_hook: Callable[[dict, str, list[dict]], dict | None] | None = None,
    track_duplicates: bool = True,
) -> dict:
    raw_dir = ROOT / "data" / "analysis" / "transcript_quality" / video_id
    meta_path = raw_dir / "raw.meta.json"
    with meta_path.open(encoding="utf-8") as f:
        raw_meta = json.load(f)
    raw_file = raw_dir / raw_meta["raw_file"]
    segments = [
        json.loads(line)
        for line in raw_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    rules = COMMON_RULES + (extra_rules or [])
    edits: dict[str, dict] = {}
    suspicious_ids: list[str] = []
    prev_text = ""

    for seg in segments:
        idx = seg["segment_index"]
        raw_text = seg["text"]

        if segment_hook:
            custom = segment_hook(seg, raw_text, suspicious_ids)
            if custom is not None:
                edits[str(idx)] = custom
                if custom.get("suspicious"):
                    suspicious_ids.append(seg["segment_id"])
                prev_text = raw_text
                continue

        if track_duplicates and raw_text == prev_text and idx > 0:
            edits[str(idx)] = {
                "ai_text": raw_text,
                "change_type": "duplicate",
                "confidence": "medium",
                "reason": "ASR lặp câu giống segment trước",
                "needs_relisten": False,
                "suspicious": True,
                "trading_term_flag": False,
            }
            suspicious_ids.append(seg["segment_id"])
            prev_text = raw_text
            continue

        prev_text = raw_text
        fixed, fix_meta = apply_rule_list(raw_text, rules)

        if fixed != raw_text or fix_meta:
            confs = [f["confidence"] for f in fix_meta]
            confidence = "low" if "low" in confs else ("medium" if "medium" in confs else "high")
            edit: dict = {
                "ai_text": fixed,
                "change_type": fix_meta[0]["change_type"] if fix_meta else "asr_term",
                "confidence": confidence,
                "reason": "; ".join(f["reason"] for f in fix_meta) if fix_meta else "Sửa ASR trên raw",
                "needs_relisten": any(f.get("needs_relisten") for f in fix_meta),
                "trading_term_flag": any(f.get("trading_term_flag") for f in fix_meta),
            }
            if any(f.get("suspicious") for f in fix_meta) or confidence == "low":
                edit["suspicious"] = True
                suspicious_ids.append(seg["segment_id"])
            edits[str(idx)] = edit

    suspicious_unique = list(dict.fromkeys(suspicious_ids))
    with tempfile.TemporaryDirectory(prefix="agent_direct_") as tmp:
        edits_path = Path(tmp) / "edits.json"
        suspicious_path = Path(tmp) / "suspicious.json"
        edits_path.write_text(json.dumps(edits, ensure_ascii=False), encoding="utf-8")
        suspicious_path.write_text(
            json.dumps(suspicious_unique, ensure_ascii=False), encoding="utf-8"
        )
        proc = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "agent_direct_clean_video.py"),
                "--edits-file",
                str(edits_path),
                "--suspicious-file",
                str(suspicious_path),
                f"--video-id={video_id}",
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
        raise SystemExit(proc.returncode)
    print(proc.stdout.strip())
    print(f"{video_id}: edits={len(edits)} suspicious={len(suspicious_ids)}", file=sys.stderr)
    return json.loads(proc.stdout.strip())
