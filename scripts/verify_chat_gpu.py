"""Quick check: llama.cpp sees CUDA and offloads at least one layer to GPU."""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path


def sanitize_cuda_path() -> None:
    cuda_path = os.environ.get("CUDA_PATH")
    if cuda_path and not (Path(cuda_path) / "lib").exists():
        os.environ.pop("CUDA_PATH", None)
    if not os.environ.get("CUDA_PATH"):
        default = Path(r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.3")
        if (default / "bin" / "nvcc.exe").exists():
            os.environ["CUDA_PATH"] = str(default)


def add_nvidia_dll_dirs() -> None:
    import site

    site_packages = Path(site.getsitepackages()[0])
    for relative in (
        "llama_cpp/lib",
        "nvidia/cublas/bin",
        "nvidia/cuda_runtime/bin",
    ):
        folder = site_packages / relative.replace("/", os.sep)
        if folder.is_dir():
            os.add_dll_directory(str(folder))

    cuda_path = os.environ.get("CUDA_PATH")
    if cuda_path:
        toolkit = Path(cuda_path)
        path_extra: list[str] = []
        for sub in ("bin/x64", "bin", "lib/x64"):
            folder = toolkit / sub.replace("/", os.sep)
            if folder.is_dir():
                os.add_dll_directory(str(folder))
                path_extra.append(str(folder))
        if path_extra:
            os.environ["PATH"] = os.pathsep.join(path_extra) + os.pathsep + os.environ.get("PATH", "")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()

    sanitize_cuda_path()
    add_nvidia_dll_dirs()

    from llama_cpp import Llama

    config_path = args.root.resolve() / "config" / "local_chat_model.toml"
    import tomllib

    with config_path.open("rb") as handle:
        cfg = tomllib.load(handle)
    model_path = args.root.resolve() / cfg["model"]["relative_dir"] / cfg["model"]["filename"]
    if not model_path.exists():
        print(f"Missing model: {model_path}", file=sys.stderr)
        return 2

    n_gpu = int(cfg.get("runtime", {}).get("n_gpu_layers", -1))
    log_lines: list[str] = []

    class Capture:
        def write(self, text: str) -> int:
            log_lines.append(text)
            return len(text)

        def flush(self) -> None:
            return None

    old_stderr = sys.stderr
    sys.stderr = Capture()
    try:
        llm = Llama(
            model_path=str(model_path),
            n_ctx=512,
            n_gpu_layers=n_gpu,
            verbose=True,
        )
        llm("ping", max_tokens=4)
    finally:
        sys.stderr = old_stderr

    blob = "".join(log_lines)
    backends = re.search(r"backend_ptrs\.size\(\) = (\d+)", blob)
    gpu_layers = len(re.findall(r"assigned to device (CUDA|GPU)", blob))
    cpu_only = backends and backends.group(1) == "1" and gpu_layers == 0

    print(f"llama backends: {backends.group(1) if backends else '?'}")
    print(f"layers on GPU: {gpu_layers}")
    if cpu_only:
        print("FAIL: only CPU backend. Run: .\\scripts\\install_chat_gpu.ps1", file=sys.stderr)
        return 1
    print("OK: GPU offload active.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
