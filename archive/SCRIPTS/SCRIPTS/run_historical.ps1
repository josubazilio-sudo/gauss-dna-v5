$env:QUANTOS_DEBUG="true"
$env:QUANTOS_ENV="development"
$env:QUANTOS_PROVIDER="historical"
Write-Host "=== QuantOS - Modo DEBUG (Historical Provider) ===" -ForegroundColor Yellow
python main.py
