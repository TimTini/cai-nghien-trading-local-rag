# Chat local — cần llama.cpp tại config [chat].llama_endpoint
# Usage: .\scripts\run_chat.ps1
#        .\scripts\run_chat.ps1 -Question "BTC có nên long không?"
param(
    [string]$Root = $PSScriptRoot + "\..",
    [string]$Question = "",
    [switch]$NoLlm
)
$args = @("run", "python", "scripts/run_chat.py", "--root", (Resolve-Path $Root).Path)
if ($Question) { $args += @("-q", $Question) }
if ($NoLlm) { $args += "--no-llm" }
& rtk @("uv") @args
