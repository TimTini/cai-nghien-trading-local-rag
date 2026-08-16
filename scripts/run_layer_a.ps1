# Lớp A — media + ASR + frame/OCR (regular + livestream)
# Usage: .\scripts\run_layer_a.ps1
#        .\scripts\run_layer_a.ps1 -Status
param(
    [string]$Root = $PSScriptRoot + "\..",
    [switch]$Status,
    [switch]$StopOnError
)
$args = @("run", "python", "scripts/run_layer_a.py", "--root", (Resolve-Path $Root).Path)
if ($Status) { $args += "--status" }
if ($StopOnError) { $args += "--stop-on-error" }
& rtk @("uv") @args
