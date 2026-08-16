# One-time rename: H:\test -> H:\cai-nghien-trading-local-rag
# Rerun-safe: skips move if target already exists and source is gone.
param(
    [string]$OldRoot = "H:\test",
    [string]$NewRoot = "H:\cai-nghien-trading-local-rag"
)

$ErrorActionPreference = "Stop"

function Update-TextFile {
    param(
        [string]$Path,
        [hashtable]$Replacements
    )
    if (-not (Test-Path -LiteralPath $Path)) { return }
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

if (Test-Path -LiteralPath $OldRoot) {
    if (Test-Path -LiteralPath $NewRoot) {
        throw "Target already exists: $NewRoot"
    }
    Move-Item -LiteralPath $OldRoot -Destination $NewRoot
    Write-Host "Renamed: $OldRoot -> $NewRoot"
}
elseif (Test-Path -LiteralPath $NewRoot) {
    Write-Host "Already renamed: $NewRoot"
}
else {
    throw "Neither old nor new project root exists."
}

$replacements = @{
    "H:\\test" = "H:\\cai-nghien-trading-local-rag"
    "H:/test" = "H:/cai-nghien-trading-local-rag"
    "H:\test" = "H:\cai-nghien-trading-local-rag"
}

$textExtensions = @(".py", ".ps1", ".md", ".json", ".jsonl", ".toml", ".txt", ".yaml", ".yml")
$skipDirs = @(".git", ".venv", ".uv", "models", "node_modules")

Get-ChildItem -LiteralPath $NewRoot -Recurse -File | Where-Object {
    $rel = $_.FullName.Substring($NewRoot.Length).TrimStart("\")
    $parts = $rel -split "\\"
    ($parts | Where-Object { $skipDirs -contains $_ }).Count -eq 0 -and
    ($textExtensions -contains $_.Extension.ToLower())
} | ForEach-Object {
    Update-TextFile -Path $_.FullName -Replacements $replacements
}

$hyperExtractRoot = "F:\MyGitProject\Hyper-Extract"
if (Test-Path -LiteralPath $hyperExtractRoot) {
    Get-ChildItem -LiteralPath $hyperExtractRoot -Recurse -File |
        Where-Object { $textExtensions -contains $_.Extension.ToLower() } |
        ForEach-Object {
            Update-TextFile -Path $_.FullName -Replacements $replacements
        }
}

Write-Host "PASS: project root is $NewRoot"
