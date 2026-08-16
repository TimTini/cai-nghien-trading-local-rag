# Remux video-light (hinh) + audio (tieng) thanh 1 file xem duoc trong Downloads.
# Vi du:
#   .\scripts\mux_video_light_to_downloads.ps1
#   .\scripts\mux_video_light_to_downloads.ps1 -VideoId D88OyuOGehY

param(
    [string]$VideoId = "D88OyuOGehY",
    [string]$OutDir = "H:\Downloads",
    [string]$ProjectRoot = ""
)

$ErrorActionPreference = "Stop"

if (-not $ProjectRoot) {
    $ProjectRoot = Split-Path -Parent $PSScriptRoot
}

$videoPath = Join-Path $ProjectRoot "data\raw\videos\$VideoId\video-light\$VideoId.mp4"
$audioPath = Join-Path $ProjectRoot "data\raw\videos\$VideoId\audio\$VideoId.m4a"
$outPath = Join-Path $OutDir "$VideoId.mkv"

if (-not (Test-Path -LiteralPath $videoPath)) {
    throw "Khong thay video-light: $videoPath"
}
if (-not (Test-Path -LiteralPath $audioPath)) {
    throw "Khong thay audio: $audioPath"
}
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    throw "Thieu ffmpeg trong PATH."
}

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

Write-Host "Mux $VideoId -> $outPath"
& ffmpeg -hide_banner -y -i $videoPath -i $audioPath -map 0:v -map 1:a -c copy $outPath
if ($LASTEXITCODE -ne 0) {
    throw "ffmpeg fail, exit $LASTEXITCODE"
}

$item = Get-Item -LiteralPath $outPath
Write-Host "PASS $($item.FullName) bytes=$($item.Length)"
