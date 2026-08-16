$stateDir = Join-Path $PSScriptRoot "..\data\analysis\state"
$replacements = @{
    'H:\\test' = 'H:\\cai-nghien-trading-local-rag'
    'H:/test' = 'H:/cai-nghien-trading-local-rag'
}

Get-ChildItem -LiteralPath $stateDir -Filter "*.json" | ForEach-Object {
    $path = $_.FullName
    $content = Get-Content -LiteralPath $path -Raw -Encoding UTF8
    $updated = $content
    foreach ($key in $replacements.Keys) {
        $updated = $updated.Replace($key, $replacements[$key])
    }
    if ($updated -ne $content) {
        Set-Content -LiteralPath $path -Value $updated -Encoding UTF8 -NoNewline
        Write-Host "Updated: $($_.Name)"
    }
}
