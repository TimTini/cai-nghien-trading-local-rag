# Finish path reference updates after rename to H:\cai-nghien-trading-local-rag
param(
    [string]$ProjectRoot = "H:\cai-nghien-trading-local-rag",
    [string]$HyperExtractRoot = "F:\MyGitProject\Hyper-Extract"
)

$ErrorActionPreference = "Stop"

$replacements = @{
    "H:\\test" = "H:\\cai-nghien-trading-local-rag"
    "H:/test" = "H:/cai-nghien-trading-local-rag"
    "H:\test" = "H:\cai-nghien-trading-local-rag"
}

$textExtensions = @(".py", ".ps1", ".md", ".json", ".jsonl", ".toml", ".txt", ".yaml", ".yml")
$skipDirs = @(".git", ".venv", ".uv", "models", "node_modules")

function Update-TextFile {
    param([string]$Path, [hashtable]$Replacements)
    $content = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
    $original = $content
    foreach ($key in $Replacements.Keys) {
        $content = $content.Replace($key, $Replacements[$key])
    }
    if ($content -ne $original) {
        Set-Content -LiteralPath $Path -Value $content -Encoding UTF8 -NoNewline
        Write-Host "Updated: $Path"
    }
}

function Update-Tree {
    param([string]$Root)
    if (-not (Test-Path -LiteralPath $Root)) { return }
    Get-ChildItem -LiteralPath $Root -Recurse -File | Where-Object {
        $ext = $_.Extension
        if ([string]::IsNullOrEmpty($ext)) { return $false }
        $rel = $_.FullName.Substring($Root.Length).TrimStart("\")
        $parts = $rel -split "\\"
        ($parts | Where-Object { $skipDirs -contains $_ }).Count -eq 0 -and
        ($textExtensions -contains $ext.ToLower())
    } | ForEach-Object {
        Update-TextFile -Path $_.FullName -Replacements $replacements
    }
}

Update-Tree -Root $ProjectRoot
Update-Tree -Root $HyperExtractRoot

$left = @()
foreach ($root in @($ProjectRoot, $HyperExtractRoot)) {
    if (-not (Test-Path -LiteralPath $root)) { continue }
    $hits = Select-String -Path (Join-Path $root "**\*") -Pattern "H:\\test|H:/test" -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -notmatch '\\(\.git|\.venv|\.uv|models)\\' } |
        Select-Object -First 5
    if ($hits) { $left += $hits }
}

if ($left.Count -gt 0) {
    Write-Host "WARN: remaining references:"
    $left | ForEach-Object { Write-Host "  $($_.Path):$($_.LineNumber)" }
    exit 1
}

Write-Host "PASS: references updated under $ProjectRoot"
