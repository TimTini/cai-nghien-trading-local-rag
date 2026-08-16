# Lớp B — normalize + clean transcript
# Usage: .\scripts\run_layer_b.ps1
#        .\scripts\run_layer_b.ps1 -AsrReprocess
param(
    [string]$Root = $PSScriptRoot + "\..",
    [switch]$ForceClean,
    [switch]$AsrReprocess
)
$args = @("run", "python", "scripts/run_layer_b.py", "--root", (Resolve-Path $Root).Path)
if ($ForceClean) { $args += "--force-clean" }
if ($AsrReprocess) { $args += "--asr-reprocess" }
& rtk @("uv") @args
