param(
    [string]$Mode = "PAPER_TRADING"
)

$env:PYTHONPATH = "C:\Users\josue\QuantOS"
$env:QUANTOS_DEBUG = "false"
$env:QUANTOS_ENV = "production"
$env:QUANTOS_MODE = $Mode.ToUpper()
$env:QUANTOS_DISCOVERY_MODE = "AUTO"
$env:QUANTOS_MAX_SCAN_PAIRS = "50"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " QUANTOS PRODUCTION MODE" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Mode:       $Mode"
Write-Host " Debug:      $env:QUANTOS_DEBUG"
Write-Host " Env:        $env:QUANTOS_ENV"
Write-Host " Discovery:  $env:QUANTOS_DISCOVERY_MODE"
Write-Host " Max pairs:  $env:QUANTOS_MAX_SCAN_PAIRS"
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

& "C:\Users\josue\QuantOS\SCRIPTS\start_quantos.ps1" -Mode $Mode
