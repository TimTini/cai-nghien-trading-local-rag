"""Export playable H.264 MP4 and blur unlicensed-exchange URL bars.

VN context (Aug 2026): Nghi dinh 284/2026 hieu luc 1/9/2026. Chua co san
quoc te (OKX/Binance/BingX/...) duoc cap phep. Script chi che vung URL
tren man hinh (thanh dia chi), khong che ten san trong UI/giao dien bot.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

VIDEO_ID = "D88OyuOGehY"
PROJECT_ROOT = Path(r"h:\cai-nghien-trading-local-rag")
OUT_DIR = Path(r"H:\Downloads")
OUT_FILE = OUT_DIR / f"{VIDEO_ID}_Bo-Loc-OI-OKX-VIC24_h264_blur-url.mp4"

EXCHANGE_MARKERS = (
    "okx.com",
    "binance.com",
    "bingx.com",
    "bitget.com",
    "bybit.com",
    "gate.io",
    "mexc.com",
    "kucoin.com",
    "huobi.com",
)

VIDEO_W = 1280
VIDEO_H = 720
PAD_X = 24
PAD_Y = 12


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def is_exchange_url(text: str) -> bool:
    lowered = text.lower().replace(" ", "")
    if "http" not in lowered and ".com" not in lowered and ".io" not in lowered:
        return False
    return any(marker in lowered for marker in EXCHANGE_MARKERS)


def clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


def padded_box(box: list[int]) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = [int(v) for v in box]
    x = clamp(x1 - PAD_X, 0, VIDEO_W - 2)
    y = clamp(y1 - PAD_Y, 0, VIDEO_H - 2)
    right = clamp(x2 + PAD_X, x + 2, VIDEO_W)
    bottom = clamp(y2 + PAD_Y, y + 2, VIDEO_H)
    return x, y, right - x, bottom - y


def collect_blur_windows() -> list[dict]:
    ocr_path = PROJECT_ROOT / "data" / "analysis" / "ocr" / VIDEO_ID / "ocr.json"
    frames_path = PROJECT_ROOT / "data" / "analysis" / "frames" / VIDEO_ID / "frames.json"
    ocr_rows = load_json(ocr_path)
    frame_rows = load_json(frames_path)
    timestamps = sorted(float(row["timestamp"]) for row in frame_rows)
    duration = 1322.89

    windows = []
    for row in ocr_rows:
        start = float(row.get("timestamp") or 0)
        next_times = [t for t in timestamps if t > start + 0.2]
        end = next_times[0] if next_times else duration
        for item in row.get("items") or []:
            text = str(item.get("text") or "")
            box = item.get("box")
            if not box or not is_exchange_url(text):
                continue
            x, y, w, h = padded_box(box)
            windows.append(
                {
                    "start": max(0.0, start - 0.5),
                    "end": min(duration, end + 0.5),
                    "x": x,
                    "y": y,
                    "w": w,
                    "h": h,
                    "text": text,
                }
            )
    return windows


def merge_same_region(windows: list[dict]) -> list[dict]:
    if not windows:
        return []
    ordered = sorted(windows, key=lambda item: (item["y"], item["x"], item["start"]))
    merged = [dict(ordered[0])]
    for item in ordered[1:]:
        last = merged[-1]
        same_place = abs(item["x"] - last["x"]) < 40 and abs(item["y"] - last["y"]) < 10
        overlap_time = item["start"] <= last["end"] + 1.0
        if same_place and overlap_time:
            last["end"] = max(last["end"], item["end"])
            last["w"] = max(last["w"], item["w"])
            last["h"] = max(last["h"], item["h"])
            continue
        merged.append(dict(item))
    return merged


def build_filter_simple(windows: list[dict]) -> str:
    """One overlay chain. Each crop comes from a fresh split of the current video."""

    if not windows:
        return "[0:v]copy[vout]"

    current = "0:v"
    parts: list[str] = []
    for index, window in enumerate(windows):
        split_left = f"s{index}a"
        split_right = f"s{index}b"
        blur_name = f"b{index}"
        out_name = "vout" if index == len(windows) - 1 else f"v{index}"
        enable = f"between(t\\,{window['start']:.3f}\\,{window['end']:.3f})"
        parts.append(f"[{current}]split=2[{split_left}][{split_right}]")
        parts.append(
            f"[{split_right}]crop={window['w']}:{window['h']}:{window['x']}:{window['y']},boxblur=5:2:3:1[{blur_name}]"
        )
        parts.append(
            f"[{split_left}][{blur_name}]overlay={window['x']}:{window['y']}:enable={enable}[{out_name}]"
        )
        current = out_name
    return ";".join(parts)


def pick_encoder() -> list[str]:
    help_text = subprocess.run(
        ["ffmpeg", "-hide_banner", "-encoders"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    if "h264_nvenc" in help_text:
        return ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "22"]
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20"]


def run_ffmpeg(windows: list[dict], *, start: float | None, duration: float | None, out_path: Path) -> None:
    video = PROJECT_ROOT / "data" / "raw" / "videos" / VIDEO_ID / "video-light" / f"{VIDEO_ID}.mp4"
    audio = PROJECT_ROOT / "data" / "raw" / "videos" / VIDEO_ID / "audio" / f"{VIDEO_ID}.m4a"
    if not video.exists() or not audio.exists():
        raise FileNotFoundError("Thieu video-light hoac audio.")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    encoder = pick_encoder()
    command = ["ffmpeg", "-hide_banner", "-y"]
    if start is not None:
        command += ["-ss", str(start)]
    command += ["-i", str(video)]
    if start is not None:
        command += ["-ss", str(start)]
    command += ["-i", str(audio)]
    if duration is not None:
        command += ["-t", str(duration)]
    command += [
        "-filter_complex",
        build_filter_simple(windows),
        "-map",
        "[vout]",
        "-map",
        "1:a",
        *encoder,
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-movflags",
        "+faststart",
        "-shortest",
        str(out_path),
    ]
    print("CMD:", " ".join(command), flush=True)
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        raise SystemExit(f"ffmpeg fail exit={completed.returncode}")


def probe(path: Path) -> None:
    subprocess.run(
        [
            "ffprobe",
            "-hide_banner",
            "-show_entries",
            "stream=codec_type,codec_name,width,height:format=duration,size",
            "-of",
            "default",
            str(path),
        ],
        check=False,
    )


def main() -> int:
    if shutil.which("ffmpeg") is None:
        print("Thieu ffmpeg trong PATH.")
        return 1
    windows = merge_same_region(collect_blur_windows())
    print("Blur windows:")
    for window in windows:
        print(
            f"  t={window['start']:.1f}-{window['end']:.1f}s "
            f"xywh={window['x']},{window['y']},{window['w']},{window['h']} "
            f"text={window['text'][:80]}"
        )
    if not windows:
        print("Khong thay URL san trong OCR. Van encode H.264 de xem duoc.")
        windows = [
            {
                "start": 0,
                "end": 0.01,
                "x": 0,
                "y": 0,
                "w": 2,
                "h": 2,
                "text": "",
            }
        ]

    test_path = OUT_DIR / f"{VIDEO_ID}_blur_url_test20s.mp4"
    okx_windows = [w for w in windows if w["start"] >= 800]
    test_windows = []
    for window in okx_windows:
        shifted = dict(window)
        shifted["start"] = max(0.0, window["start"] - 875.0)
        shifted["end"] = max(0.1, window["end"] - 875.0)
        test_windows.append(shifted)
    print("\n=== test clip 20s around OKX URL ===", flush=True)
    run_ffmpeg(test_windows or windows[:1], start=875.0, duration=20.0, out_path=test_path)
    probe(test_path)

    print("\n=== full export ===", flush=True)
    run_ffmpeg(windows, start=None, duration=None, out_path=OUT_FILE)
    probe(OUT_FILE)
    print(f"PASS {OUT_FILE} bytes={OUT_FILE.stat().st_size}")
    print(f"PASS test {test_path} bytes={test_path.stat().st_size}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
