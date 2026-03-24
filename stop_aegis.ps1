$ErrorActionPreference = "SilentlyContinue"
$Root   = Split-Path $MyInvocation.MyCommand.Path -Parent
$RunDir = Join-Path $Root "run"

function Stop-ByPidFile {
    param($name)
    $pidFile = Join-Path $RunDir "$name.pid"
    if (Test-Path $pidFile) {
        $procId = Get-Content $pidFile | Select-Object -First 1
        if ($procId) {
            Write-Host "Stopping $name (PID $procId)..."
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        }
        Remove-Item $pidFile -ErrorAction SilentlyContinue
    }
}

Stop-ByPidFile "backend"
Stop-ByPidFile "broker"

Write-Host "Stop command issued. If mosquitto was started manually, you may still need to close it."
