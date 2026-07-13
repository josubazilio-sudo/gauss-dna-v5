param(
    [string]$Mode = "DEVELOPMENT"
)

$env:PYTHONPATH = "C:\Users\josue\QuantOS"
$env:QUANTOS_MODE = $Mode.ToUpper()

$validModes = @("DEVELOPMENT", "PAPER_TRADING", "LIVE")
if ($env:QUANTOS_MODE -notin $validModes) {
    Write-Host "Modo invalido: $Mode"
    Write-Host "Modos suportados: DEVELOPMENT, PAPER_TRADING, LIVE"
    exit 1
}

Write-Host "Iniciando QuantOS em modo: $env:QUANTOS_MODE"

python -c "
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('quantos.log', mode='a'),
        logging.StreamHandler(sys.stdout)
    ]
)

from main import QuantOSApp
from CORE.data_providers import create_provider
from CORE.execution.mode_manager import ExecutionModeManager

mode = ExecutionModeManager()
print('QuantOS iniciando em modo:', mode.mode_name)
provider = create_provider()
app = QuantOSApp(provider)

try:
    app.start()
except KeyboardInterrupt:
    app.stop()
" 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host "QuantOS encerrado com erro (codigo: $LASTEXITCODE)" -ForegroundColor Red
}
