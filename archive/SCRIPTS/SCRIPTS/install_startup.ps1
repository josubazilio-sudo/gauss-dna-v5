param(
    [string]$Mode = "DEVELOPMENT"
)

$ErrorActionPreference = "Stop"

$taskName = "QuantOS"
$quantosDir = "C:\Users\josue\QuantOS"
$psScript = "$quantosDir\SCRIPTS\run_daemon.ps1"
$logDir = "$quantosDir\LOGS"
$stdoutLog = "$logDir\stdout.log"
$stderrLog = "$logDir\stderr.log"

if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

# Create the runner script that launches QuantOS silently
@"
param()
`$env:PYTHONPATH = "$quantosDir"
`$env:QUANTOS_MODE = "$Mode".ToUpper()
Set-Location "$quantosDir"
python main.py 2>&1 >> "$stdoutLog"
"@ | Set-Content -Path $psScript -Encoding UTF8

# Register the scheduled task
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-WindowStyle Hidden -ExecutionPolicy Bypass -File `"$psScript`""

$trigger = New-ScheduledTaskTrigger -AtLogOn -User "josue"
$trigger.Delay = "PT30S"  # 30 second delay after login

$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -Priority 5

$principal = New-ScheduledTaskPrincipal -UserId "josue" -LogonType S4U -RunLevel Limited

try {
    $existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($existing) {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
        Write-Host "Task '$taskName' existente removida."
    }
    
    Register-ScheduledTask -TaskName $taskName `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Principal $principal `
        -Description "QuantOS - Inicializacao automatica do sistema de trading quantitativo" `
        -Force

    Write-Host ""
    Write-Host "✅ TASK '$taskName' REGISTRADA COM SUCESSO!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Detalhes:" -ForegroundColor Cyan
    Write-Host "  Script:      $psScript"
    Write-Host "  Modo:        $Mode"
    Write-Host "  Disparo:     Ao fazer login (delay 30s)"
    Write-Host "  Usuário:     josue"
    Write-Host "  Log stdout:  $stdoutLog"
    Write-Host "  Log stderr:  $stderrLog"
    Write-Host ""
    Write-Host "Para testar agora:" -ForegroundColor Yellow
    Write-Host "  Start-ScheduledTask -TaskName '$taskName'"
    Write-Host ""
    Write-Host "Para remover:" -ForegroundColor Yellow
    Write-Host "  Unregister-ScheduledTask -TaskName '$taskName' -Confirm:`$false"
    
} catch {
    Write-Host "❌ ERRO: $_" -ForegroundColor Red
    exit 1
}
