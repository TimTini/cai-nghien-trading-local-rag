# Lớp C — build-index (approved ưu tiên, chưa approve thì ai_cleaned)
# Usage: .\scripts\run_layer_c.ps1
#        .\scripts\run_layer_c.ps1 -ReviewUi
param(
    [string]$Root = $PSScriptRoot + "\..",
    [switch]$ReviewUi,
    [int]$Port = 0
)
$args = @("run", "python", "scripts/run_layer_c.py", "--root", (Resolve-Path $Root).Path)
if ($ReviewUi) { $args += "--review-ui" }
if ($Port -gt 0) { $args += @("--port", "$Port") }
& rtk @("uv") @args
