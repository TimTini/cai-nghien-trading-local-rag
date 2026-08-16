# Chat GGUF local + RAG (GPU nếu đã cài install_chat_gpu.ps1)
param(
    [string]$Root = (Join-Path $PSScriptRoot ".."),
    [string]$Question = ""
)
if ($env:CUDA_PATH -and -not (Test-Path (Join-Path $env:CUDA_PATH "lib"))) {
    Remove-Item Env:CUDA_PATH -ErrorAction SilentlyContinue
}
$args = @("run", "--extra", "chat", "python", "scripts/local_console_chat.py", "--root", (Resolve-Path $Root).Path)
if ($Question) { $args += @("-q", $Question) }
& rtk @("uv") @args
