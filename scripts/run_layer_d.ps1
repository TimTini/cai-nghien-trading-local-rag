param(
    [string]$Root = "H:\cai-nghien-trading-local-rag",
    [switch]$Force
)

$args = @("--root", $Root)
if ($Force) { $args += "--force" }
rtk uv run python (Join-Path $PSScriptRoot "run_layer_d.py") @args
