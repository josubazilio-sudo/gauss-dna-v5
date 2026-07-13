Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "powershell.exe -ExecutionPolicy Bypass -WindowStyle Hidden -File C:\Users\josue\QuantOS\SCRIPTS\start_quantos.ps1", 0, False
