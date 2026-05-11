$ErrorActionPreference = "Stop"
$Root     = Split-Path $MyInvocation.MyCommand.Path -Parent
$LogsDir  = Join-Path $Root "logs"
$RunDir   = Join-Path $Root "run"
$BrokerExe   = Join-Path $Root "build\mosqdl\inst\mosquitto.exe"
$BrokerConf  = Join-Path $Root "build\mosqdl\inst\mosq-open.conf"
$PythonExe   = Join-Path $Root ".venv\Scripts\python.exe"
$BackendArgs = @("-m","core.main")
$VisualCorePath = Join-Path $Root "saturday-core\bin\Release\saturday-core.exe"
New-Item -ItemType Directory -Force -Path $LogsDir | Out-Null
New-Item -ItemType Directory -Force -Path $RunDir  | Out-Null
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "     SATURDAY VISUAL CORE INITIALIZING..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
if (Test-Path $VisualCorePath) {
    Write-Host "[1/3] Launching Visual Core..." -ForegroundColor Yellow
    try {
        Start-Process -FilePath $VisualCorePath -Wait -WindowStyle Hidden
        Write-Host "[OK] Visual Core startup animation complete" -ForegroundColor Green
    } catch {
        Write-Host "[WARN] Visual Core failed: $_" -ForegroundColor Yellow
    }
} else {
    Write-Host "[SKIP] Visual Core not found at: $VisualCorePath" -ForegroundColor Yellow
}
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "     SATURDAY OS CORE INITIALIZING..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
function Test-PortListening {
    param($Port)
    try {
        $conn = Get-NetTCPConnection -LocalPort $Port -ErrorAction Stop
        return $conn.State -contains 'Listen'
    } catch {
        return $false
    }
}
if (Test-Path $BrokerExe) {
    if (-not (Test-PortListening 1884)) {
        Write-Host "Starting mosquitto on 0.0.0.0:1884..."
        $brokerProc = Start-Process -FilePath $BrokerExe `
            -ArgumentList @("-c",$BrokerConf,"-v") `
            -WorkingDirectory (Split-Path $BrokerExe -Parent) `
            -RedirectStandardOutput (Join-Path $LogsDir "mosquitto.out") `
            -RedirectStandardError  (Join-Path $LogsDir "mosquitto.err") `
            -WindowStyle Hidden `
            -PassThru
        $brokerProc.Id | Out-File (Join-Path $RunDir "broker.pid") -Encoding ascii
    } else {
        Write-Host "Mosquitto already listening on port 1884."
    }
} else {
    Write-Warning "Mosquitto binary not found at $BrokerExe"
}
$BackendPidFile = Join-Path $RunDir "backend.pid"
$backendRunning = $false
if (Test-Path $BackendPidFile) {
    $existingPid = Get-Content $BackendPidFile | Select-Object -First 1
    if ($existingPid -and (Get-Process -Id $existingPid -ErrorAction SilentlyContinue)) {
        $backendRunning = $true
    } else {
        Remove-Item $BackendPidFile -ErrorAction SilentlyContinue
    }
}
if (-not $backendRunning) {
    Write-Host "Starting SATURDAY backend..."
    $backendProc = Start-Process -FilePath $PythonExe `
        -ArgumentList $BackendArgs `
        -WorkingDirectory $Root `
        -RedirectStandardOutput (Join-Path $LogsDir "backend.out") `
        -RedirectStandardError  (Join-Path $LogsDir "backend.err") `
        -WindowStyle Hidden `
        -PassThru
    $backendProc.Id | Out-File $BackendPidFile -Encoding ascii
} else {
    Write-Host "SATURDAY backend already running (PID recorded)."
}
Write-Host "Done. Logs: $LogsDir"
