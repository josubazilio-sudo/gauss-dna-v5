param()
$env:PYTHONPATH = "C:\Users\josue\QuantOS"
$env:QUANTOS_MODE = "PAPER_TRADING".ToUpper()
Set-Location "C:\Users\josue\QuantOS"
python main.py 2>&1 >> "C:\Users\josue\QuantOS\LOGS\stdout.log"
