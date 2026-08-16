# Cài llama-cpp-python có CUDA cho RTX 4070 (Ada sm89) + chat local GGUF.
# Chạy trong PowerShell tại thư mục repo:
#   cd H:\cai-nghien-trading-local-rag
#   .\scripts\install_chat_gpu.ps1
#
# Yêu cầu: NVIDIA driver + CUDA Toolkit (winget: Nvidia.CUDA) hoặc chấp nhận UAC khi winget hỏi.
# Sau khi cài CUDA, script build lại llama-cpp-python với GGML_CUDA=on.

param(
    [string]$Root = (Join-Path $PSScriptRoot ".."),
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path $Root).Path
Set-Location $Root

# CUDA_PATH trỏ MinerU cũ sẽ làm import llama_cpp lỗi — bỏ trong phiên này.
if ($env:CUDA_PATH -and -not (Test-Path (Join-Path $env:CUDA_PATH "lib"))) {
    Remove-Item Env:CUDA_PATH -ErrorAction SilentlyContinue
    Write-Host "Removed invalid CUDA_PATH (MinerU path missing lib/)."
}

Write-Host "Installing NVIDIA runtime wheels for cuBLAS..."
& rtk uv pip install "nvidia-cuda-runtime>=13" "nvidia-cublas-cu12>=12.9" 2>&1 | Out-Host

if (-not $SkipBuild) {
    $cudaPath = [Environment]::GetEnvironmentVariable("CUDA_PATH", "Machine")
    if (-not $cudaPath) {
        $cudaPath = "C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.3"
    }
    if (-not (Test-Path (Join-Path $cudaPath "bin\nvcc.exe"))) {
        Write-Host ""
        Write-Host "CUDA Toolkit not found at: $cudaPath"
        Write-Host "Install with: winget install -e --id Nvidia.CUDA"
        Write-Host "Then re-run: .\scripts\install_chat_gpu.ps1"
        Write-Host ""
        Write-Host "Trying prebuilt Ada wheel (may stay CPU if cublas DLL missing)..."
        & rtk uv pip install --reinstall --no-deps `
            "https://github.com/dougeeai/llama-cpp-python-wheels/releases/download/v0.3.20-cuda13.0-sm89/llama_cpp_python-0.3.20%2Bcuda13.0.sm89.ada-py3-none-win_amd64.whl" 2>&1 | Out-Host
        exit 2
    }

    $env:CUDA_PATH = $cudaPath
    $env:CMAKE_ARGS = "-DGGML_CUDA=on -DCMAKE_CUDA_ARCHITECTURES=89"
    $env:FORCE_CMAKE = "1"
    Write-Host "Building llama-cpp-python with CUDA at $cudaPath (sm89, ~5-15 min)..."
    & rtk uv pip install "llama-cpp-python==0.3.25" --no-cache-dir --force-reinstall 2>&1 | Out-Host
}

Write-Host "Verifying GPU backends..."
$env:CUDA_PATH = $null
& rtk uv run --extra chat python scripts/verify_chat_gpu.py --root $Root 2>&1 | Out-Host
