param(
    [string]$Mql5Root
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$source = Join-Path $projectRoot "indicators\mt5\SBWeeklyTemplate.mq5"

if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
    throw "Indicator source was not found: $source"
}

$sourceLines = (Get-Content -LiteralPath $source).Count
if ($sourceLines -lt 800) {
    throw "Indicator source is incomplete ($sourceLines lines). Run git pull and retry."
}

if ($Mql5Root) {
    $roots = @((Resolve-Path -LiteralPath $Mql5Root).Path)
} else {
    $terminalRoot = Join-Path $env:APPDATA "MetaQuotes\Terminal"
    $roots = @(
        Get-ChildItem -LiteralPath $terminalRoot -Directory -ErrorAction SilentlyContinue |
            ForEach-Object { Join-Path $_.FullName "MQL5" } |
            Where-Object { Test-Path -LiteralPath $_ -PathType Container }
    )
}

if ($roots.Count -eq 0) {
    throw "No MT5 MQL5 data folder was found. Pass it explicitly with -Mql5Root."
}

if ($roots.Count -gt 1) {
    Write-Host "Multiple MT5 data folders were found:" -ForegroundColor Yellow
    $roots | ForEach-Object { Write-Host "  $_" }
    throw "Run again with: -Mql5Root '<the MQL5 folder shown by MT5 File > Open Data Folder>'"
}

$destinationDirectory = Join-Path $roots[0] "Indicators\My Indicators"
$destination = Join-Path $destinationDirectory "SBWeeklyTemplate.mq5"
New-Item -ItemType Directory -Path $destinationDirectory -Force | Out-Null
Copy-Item -LiteralPath $source -Destination $destination -Force

$sourceHash = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
$destinationHash = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash
$destinationLines = (Get-Content -LiteralPath $destination).Count

if ($sourceHash -ne $destinationHash -or $sourceLines -ne $destinationLines) {
    throw "Indicator verification failed after copying to MT5."
}

Write-Host ""
Write-Host "SBWeeklyTemplate installed successfully." -ForegroundColor Green
Write-Host "Destination: $destination"
Write-Host "Lines:       $destinationLines"
Write-Host "SHA256:      $destinationHash"
Write-Host ""
Write-Host "Close any old SBWeeklyTemplate tab without saving, reopen it from Navigator, then press F7."
